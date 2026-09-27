/** One-time authoring of navigation-only state assets; never used by the compiler. */
import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Document, NodeIO } from "@gltf-transform/core";
import { IDENTITY_TRANSFORM, type ProtoLevel, type Vec3 } from "@rle/shared";
import { heightPlane, planeHeight } from "../../shared/src/gameplay-plane.ts";
import { navigationStateAsset } from "./navigation-state-asset.ts";
import { recoverMotionStates } from "./recover-motion-states.ts";
import { recoverEndpointElevation, distanceToPolygon } from "./recovery-elevation.ts";
import { compactStoredMap, readStoredMap } from "./stored-map.ts";
import { sha256 } from "./bundle-asset-states.ts";
import type { GameplayOwnershipCatalog } from "./nonrendering-gameplay-owners.ts";

export async function stageNavigationStateAssets(options: {
  library: string;
  map: string;
  source: string;
  out: string;
  ownership?: string;
}) {
  const library = path.resolve(options.library),
    out = path.resolve(options.out);
  if (out === library || out.startsWith(`${library}${path.sep}`))
    throw new Error("Output must be outside the input library");
  const document = await readStoredMap(options.map, library);
  const proto: ProtoLevel = JSON.parse(await fs.readFile(options.source, "utf8"));
  const catalog: GameplayOwnershipCatalog = options.ownership
    ? JSON.parse(await fs.readFile(options.ownership, "utf8"))
    : { groups: [] };
  const map = (document.sourceMap ?? document.map).toLowerCase();
  if (!/^[a-z0-9][a-z0-9-]*$/.test(map)) throw new Error("Expected a safe map ID");
  const outputs: (ReturnType<typeof navigationStateAsset> & { patch: number })[] = [];
  const unresolved: { patch: number; error: string }[] = [];
  let sector = 0;
  for (const [layer, areas] of proto.motion_data.layers.entries())
    for (const motion of areas) {
      const identity = sector;
      sector += 1 + motion.obstacles.length;
      const { transitions } = recoverMotionStates(motion, identity, layer, proto.patches);
      for (const change of transitions) {
        if (change.patches.length !== 1) continue;
        const index = change.patches[0]!,
          patch = proto.patches[index]!;
        // Visible/effectful changes need their corresponding physical asset, not a proxy.
        if (
          patch.old_sight_obstacles.length ||
          patch.new_sight_obstacles.length ||
          patch.old_masks.length ||
          patch.new_masks.length ||
          patch.door_indices.length ||
          patch.element_fx.sprite.frame_profile_name !== "pixel_vert"
        )
          continue;
        try {
          if (catalog.movement_transitions?.some((entry) => entry.patch === index))
            throw new Error("Navigation state already has an explicit owner");
          const id = `${map}-navigation-boundary-${String(index + 1).padStart(3, "0")}`;
          if (
            document.assetSources?.some((entry) => entry.id === id) ||
            document.groups.some((group) => group.id === id)
          )
            throw new Error(`Asset already exists: ${id}`);
          const supports = proto.sight_obstacles.filter(
            (obstacle) =>
              Array.isArray(obstacle.projection_area) &&
              obstacle.projection_area[0] === patch.sector &&
              obstacle.projection_area[1] === patch.layer,
          );
          const waypointHeight = recoverEndpointElevation(
            supports.map((obstacle) => ({
              distance: distanceToPolygon(
                patch.waypoint,
                obstacle.points.map((point) => [point.x, point.y - point.z_top]),
              ),
              height: planeHeight(
                heightPlane(
                  obstacle.points
                    .slice(0, 3)
                    .map((point): Vec3 => [point.x, point.y - point.z_top, point.z_top]),
                ),
                patch.waypoint,
              ),
              maximumHeight: Math.max(
                ...obstacle.points.map((point) => Math.max(point.z_top, point.z_bottom)),
              ),
            })),
            patch.layer === 0,
          );
          const result = navigationStateAsset({
            id,
            map,
            camera: document.camera,
            patch,
            initial: change.initial,
            applied: change.applied,
            waypointHeight,
            groundLayer: layer === 0,
            receivers: proto.sight_obstacles.filter(
              (obstacle) =>
                Array.isArray(obstacle.projection_area) &&
                obstacle.projection_area[0] === identity &&
                obstacle.projection_area[1] === layer,
            ),
          });
          outputs.push({ ...result, patch: index });
          (catalog.movement_transitions ??= []).push({
            patch: index,
            owner: id,
            node: result.node,
          });
        } catch (error) {
          unresolved.push({ patch: index, error: String(error) });
        }
      }
    }
  if (!outputs.length)
    throw new Error(`No navigation-only assets staged: ${JSON.stringify(unresolved)}`);
  await fs.mkdir(out);
  await fs.mkdir(path.join(out, "3d-assets"));
  await fs.mkdir(path.join(out, "scenes"));
  for (const entry of await fs.readdir(library))
    if (!["3d-assets", "scenes"].includes(entry))
      await fs.symlink(path.join(library, entry), path.join(out, entry));
  for (const entry of await fs.readdir(path.join(library, "3d-assets"))) {
    if (entry === "index.json") continue;
    if (outputs.some((output) => output.descriptor.id === entry))
      throw new Error(`Asset directory exists: ${entry}`);
    await fs.symlink(path.join(library, "3d-assets", entry), path.join(out, "3d-assets", entry));
  }
  const sceneName = path.basename(options.map);
  for (const entry of await fs.readdir(path.join(library, "scenes")))
    if (entry !== sceneName)
      await fs.symlink(path.join(library, "scenes", entry), path.join(out, "scenes", entry));
  const index = JSON.parse(await fs.readFile(path.join(library, "3d-assets/index.json"), "utf8"));
  for (const { descriptor, origin, node } of outputs) {
    const id = descriptor.id,
      assetDir = `3d-assets/${id}`;
    const model = new Document(),
      scene = model.createScene("default");
    const mapRoot = model.createNode("map").setRotation([-Math.SQRT1_2, 0, 0, Math.SQRT1_2]);
    const group = model.createNode(id).setExtras({ asset_group: id });
    group.addChild(model.createNode(node).setExtras({ scenery: true, gameplay_only: true }));
    mapRoot.addChild(group);
    scene.addChild(mapRoot);
    model.getRoot().setDefaultScene(scene);
    const modelBytes = await new NodeIO().writeBinary(model);
    const descriptorBytes = JSON.stringify(descriptor, null, 2) + "\n";
    await fs.mkdir(path.join(out, assetDir));
    await fs.writeFile(path.join(out, assetDir, "model.glb"), modelBytes);
    await fs.writeFile(path.join(out, assetDir, "asset.json"), descriptorBytes);
    index.assets.push({
      id,
      name: descriptor.name,
      source_map: descriptor.source_map,
      descriptor: `${id}/asset.json`,
      descriptor_sha256: sha256(descriptorBytes),
      model: `${id}/model.glb`,
      model_sha256: sha256(modelBytes),
      model_scene: "default",
      editor: descriptor,
    });
    (document.assetSources ??= []).push({
      id,
      descriptor: `${assetDir}/asset.json`,
      descriptor_sha256: sha256(descriptorBytes),
      model: `${assetDir}/model.glb`,
      model_sha256: sha256(modelBytes),
      model_scene: "default",
      resources: [],
    });
    document.groups.push({
      id,
      name: descriptor.name,
      transform: { dx: origin[0], dy: origin[1], dz: origin[2], rot_deg: 0 },
    });
    document.objects.push({
      id: `${id}-frame`,
      node: `asset:${id}:${node}`,
      group: id,
      kind: "scenery",
      source: { map },
      name: "Navigation boundary",
      transform: { ...IDENTITY_TRANSFORM },
    });
  }
  await fs.writeFile(path.join(out, "3d-assets/index.json"), JSON.stringify(index, null, 2) + "\n");
  const scene = path.join(out, "scenes", sceneName);
  await fs.writeFile(scene, JSON.stringify(await compactStoredMap(document, out), null, 2) + "\n");
  await readStoredMap(scene, out);
  const ownership = path.join(out, `${map}-navigation-ownership.json`);
  // Never replace an inherited catalog through a symlink.
  await fs.writeFile(ownership, JSON.stringify(catalog, null, 2) + "\n", { flag: "wx" });
  return {
    library: out,
    scene,
    ownership,
    assets: outputs.map((output) => output.descriptor.id),
    unresolved,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [library, map, source, out, ownership] = process.argv.slice(2);
  if (!library || !map || !source || !out)
    throw new Error(
      "Usage: stage-navigation-state-assets.ts LIBRARY MAP SOURCE_JSON OUT [OWNERSHIP_JSON]",
    );
  console.log(
    JSON.stringify(
      await stageNavigationStateAssets({ library, map, source, out, ownership }),
      null,
      2,
    ),
  );
}
