import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import {
  parseSceneDoc,
  parseLevel3D,
  documentProvenance,
  IDENTITY_TRANSFORM,
  groupObstacles,
  snapFloatingParts,
  authoredAssetGroups,
  obstaclePartIdentity,
  componentIdentityMatches,
  upgradeGeneratedAssetGroups,
  type AuthoredAssetCatalog,
  type AuthoredAssetPart,
  type Level3D,
  type Level3DGroup,
  type Level3DObject,
} from "@rle/shared";
import { listFiles, readJson, subdir } from "./fs.ts";
import { loadProtoLevel, type DatadirIndex } from "./datadir.ts";
import { prepareProjectionAsset } from "./projection-library.ts";
import { disposeObjectResources } from "./resources.ts";

const groupId = (root: number) => `group-${String(root).padStart(3, "0")}`;

/** Fully validate a replacement without publishing document or viewport state.
 * The caller owns the returned asset and must dispose it if publication is stale.
 * Any failure during preparation disposes the uncommitted asset here.
 */
export async function prepareMapCandidate(
  name: string,
  library: FileSystemDirectoryHandle,
  idx: DatadirIndex | null,
  onProgress?: (completed: number, total: number, phase: string) => void,
) {
  let asset: THREE.Object3D | null = null;
  try {
    const dir = await subdir(library, ["scenes"]);
    if (!dir) throw new Error("scenes/ missing");
    const glbName = `${name}-volumes.scene.glb`;
    const sceneDoc = parseSceneDoc(
      await readJson<unknown>(dir, `${name}-volumes.scene.json`),
    );
    onProgress?.(0, 1, "Reading map");
    if (sceneDoc.map.toLowerCase() !== name.toLowerCase()) {
      throw new Error(
        `${name}-volumes.scene.json: source map is ${sceneDoc.map}`,
      );
    }
    const lvl = idx && !sceneDoc.standalone ? await loadProtoLevel(idx, sceneDoc.map) : null;
    const file = await (await dir.getFileHandle(glbName)).getFile();
    const bytes = await file.arrayBuffer();
    const provenance = await documentProvenance(lvl, bytes);
    const gltf = await new GLTFLoader().parseAsync(bytes, "");
    asset = gltf.scene;
    const nextSources = new Map<string, THREE.Object3D>();
    let nextGround: THREE.Object3D | null = null;
    const root =
      gltf.scene.children.find((c) => c.name === "map") ?? gltf.scene;
    for (const child of [...root.children]) {
      if (child.name === "ground") nextGround = child;
      else
        for (const node of child.children) {
          if (nextSources.has(node.name))
            throw new Error(`Duplicate GLB node ${node.name}`);
          nextSources.set(node.name, node);
        }
    }
    const exportedGroups = root.children.filter(child => child.name !== "ground");
    let exportedCatalog: AuthoredAssetCatalog | undefined;
    if (exportedGroups.some(group => group.userData.asset_group !== undefined)) {
      exportedCatalog = {
        map: sceneDoc.map,
        groups: exportedGroups.map(group => {
          const id: unknown = group.userData.asset_group;
          const label: unknown = group.userData.asset_name ?? group.userData.name ?? group.name;
          if (typeof id !== "string" || !id.trim() || typeof label !== "string" || !label.trim())
            throw new Error("Incomplete authored GLB group metadata");
          return { id, name: label, parts: group.children.map((node): AuthoredAssetPart => {
            const identity = obstaclePartIdentity(node.name);
            const obstacle: unknown = node.userData.source_obstacle;
            const partName: unknown = node.userData.part_name;
            if (/^mission-[a-zA-Z0-9_-]+$/.test(node.name)) {
              const profile: unknown = node.userData.mission_patch_profile;
              if (obstacle !== undefined || typeof profile !== "string" || !profile.trim() ||
                  typeof partName !== "string" || !partName.trim() || !node.userData.obstacle_local_game)
                throw new Error(`Invalid authored mission part metadata: ${node.name}`);
              return { node: node.name, name: partName, mission_profile: profile,
                obstacle_local_game: node.userData.obstacle_local_game };
            }
            if (!identity || !componentIdentityMatches(node.name, obstacle, node.userData.source_components) || typeof partName !== "string" || !partName.trim())
              throw new Error(`Invalid authored GLB part metadata: ${node.name}`);
            if (identity.component && !node.userData.obstacle_local_game) throw new Error(`Missing component footprint: ${node.name}`);
            return { obstacle: identity.obstacle, name: partName, ...(identity.component ? { node: node.name, components: [identity.component], obstacle_local_game: node.userData.obstacle_local_game } : {}) };
          }) };
        }),
      };
    }
    const nextSuspects = new Map<number, { delta: number; support: number }>();
    let d: Level3D | null = null;
    let upgradedGroups = false;
    const docName = `${name}.level3d.json`;
    const files = await listFiles(dir);
    if (files.includes(docName)) {
      const saved = parseLevel3D(await readJson<unknown>(dir, docName), {
        map: sceneDoc.map, glb: glbName, level: lvl ?? undefined,
      });
      const references = saved.assetSources ?? [];
      const preparedSources = new Array<Awaited<ReturnType<typeof prepareProjectionAsset>>>(references.length);
      let nextReference = 0;
      let failed = false;
      let failure: unknown;
      const loadNext = async () => {
        while (!failed && nextReference < references.length) {
          const index = nextReference++;
          const reference = references[index]!;
          try {
            const prepared = await prepareProjectionAsset(library, reference, sceneDoc.map, reference);
            // Transfer ownership immediately, including completions after another
            // worker failed. The outer catch retires everything after workers settle.
            asset!.add(prepared.asset);
            preparedSources[index] = prepared;
            onProgress?.(preparedSources.filter(Boolean).length, references.length, "Loading assets");
          } catch (error) {
            if (!failed) { failed = true; failure = error; }
          }
        }
      };
      // Limit simultaneous model decoding and texture allocation on large maps.
      await Promise.all(Array.from({ length: Math.min(4, references.length) }, loadNext));
      if (failed) throw failure;
      onProgress?.(references.length, references.length, "Finalizing map");
      for (const prepared of preparedSources) {
        asset.add(prepared.asset); // Retain document order regardless of completion order.
        for (const [key, node] of prepared.sources) {
          if (nextSources.has(key)) throw new Error(`Duplicate standalone source node ${key}`);
          nextSources.set(key, node);
        }
      }
      d = parseLevel3D(saved, {
        map: sceneDoc.map,
        glb: glbName,
        level: lvl ?? undefined,
        nodes: new Set(nextSources.keys()),
      });
      upgradedGroups = upgradeGeneratedAssetGroups(d, exportedCatalog);
      if (lvl) {
        const terraces = new Set(
          d.objects
            .filter((o) => o.kind === "terrace")
            .flatMap((o) => o.source.obstacle === undefined ? [] : [o.source.obstacle]),
        );
        const sus = new Map<number, { delta: number; support: number }>();
        for (const x of snapFloatingParts(lvl.sight_obstacles, terraces, {
          includeOpaque: true,
        }).snapped)
          sus.set(x.index, { delta: x.delta, support: x.support });
        for (const [key, value] of sus) nextSuspects.set(key, value);
      }
    }
    if (!d) {
      if (!lvl)
        throw new Error(
          "connect the datadir to build the level document from the game data",
        );
      const objects: Level3DObject[] = [];
      const terraces = new Set<number>();
      for (const nodeName of [...nextSources.keys()].sort()) {
        const identity = obstaclePartIdentity(nodeName);
        if (!identity) continue;
        const obstacle = identity.obstacle;
        if (identity.kind === "terrace") terraces.add(obstacle);
        objects.push({
          id: nodeName,
          kind: identity.kind,
          node: nodeName,
          source: { map: sceneDoc.map, obstacle, ...(identity.component ? { components: [identity.component] } : {}) },
          obstacle: identity.component ? structuredClone(nextSources.get(nodeName)!.userData.obstacle_local_game) : lvl.sight_obstacles[obstacle]!,
          transform: { ...IDENTITY_TRANSFORM },
        });
      }
      for (const group of exportedCatalog?.groups ?? []) for (const part of group.parts) {
        if (part.mission_profile === undefined) continue;
        objects.push({ id: part.node, node: part.node, kind: "mission", name: part.name,
          source: { map: sceneDoc.map, mission_profile: part.mission_profile },
          obstacle: structuredClone(part.obstacle_local_game!), transform: { ...IDENTITY_TRANSFORM } });
      }
      // buildings: parts stacked on the same footprint
      const groupOf = groupObstacles(lvl.sight_obstacles, terraces);
      // parts that may be stored displaced along the view ray: offered as a per-part snap, never applied automatically
      const sus = new Map<number, { delta: number; support: number }>();
      for (const x of snapFloatingParts(lvl.sight_obstacles, terraces, {
        includeOpaque: true,
      }).snapped)
        sus.set(x.index, { delta: x.delta, support: x.support });
      for (const [key, value] of sus) nextSuspects.set(key, value);
      const groups: Level3DGroup[] = [];
      const seen = new Set<string>();
      for (const o of objects) {
        if (o.source.obstacle === undefined) continue;
        const root = groupOf.get(o.source.obstacle);
        if (root === undefined) continue;
        o.group = groupId(root);
        if (!seen.has(o.group)) {
          seen.add(o.group);
          groups.push({ id: o.group, transform: { ...IDENTITY_TRANSFORM } });
        }
      }
      d = {
        version: 1,
        map: sceneDoc.map,
        size: sceneDoc.size,
        camera: sceneDoc.camera,
        glb: glbName,
        objects,
        groups: authoredAssetGroups(sceneDoc.map, objects, exportedCatalog) ?? groups,
      };
    }
    for (const part of d.objects) {
      if (part.kind !== "mission" || part.node.startsWith("asset:")) continue;
      const node = nextSources.get(part.node);
      if (!node || node.userData.mission_patch_profile !== part.source.mission_profile)
        throw new Error(`Mission source profile mismatch: ${part.node}`);
    }
    parseLevel3D(d, {
      scene: sceneDoc,
      map: sceneDoc.map,
      glb: glbName,
      level: lvl ?? undefined,
      nodes: new Set(nextSources.keys()),
      sourceSha256: provenance.source_sha256,
      glbSha256: provenance.glb_sha256,
    });
    const hadProvenance = !!d.provenance;
    d = {
      ...d,
      provenance: {
        ...d.provenance,
        ...provenance,
        source_sha256: provenance.source_sha256 ?? d.provenance?.source_sha256,
      },
    };

    return {
      name,
      document: d,
      directory: dir,
      level: lvl,
      sources: nextSources,
      ground: nextGround,
      suspects: nextSuspects,
      asset,
      saved: files.includes(docName) && hadProvenance && !upgradedGroups,
    };
  } catch (error) {
    if (asset) disposeObjectResources([asset]);
    throw error;
  }
}
