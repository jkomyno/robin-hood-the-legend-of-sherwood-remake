/** Offline authoring: combine complete static assets in a reviewed common frame. */
import { Document, NodeIO, Scene } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { mergeDocuments, unpartition } from "@gltf-transform/functions";
import {
  gameToScene,
  sceneToGltf,
  isIdentity,
  assetNodeKey,
  transformedObstacle,
  type Level3D,
  type ProjectionAssetDescriptor,
} from "@rle/shared";
import { canonical, modelContentSignatures } from "./bundle-asset-states.ts";
import { normalizeStaticAssetModel, verifyStaticParts } from "./static-asset-model.ts";

export interface StaticAssetInput {
  descriptor: ProjectionAssetDescriptor;
  model: Document;
}

export function assertStaticDescriptor(descriptor: ProjectionAssetDescriptor) {
  const supported = new Set([
    "version",
    "kind",
    "id",
    "name",
    "source_map",
    "source_origin_scene",
    "model",
    "model_scene",
    "resources",
    "parts",
  ]);
  if (Object.keys(descriptor).some((key) => !supported.has(key)))
    throw new Error(`Asset requires explicit metadata migration: ${descriptor.id}`);
}

/** The catalog must describe exactly the complete parts of the selected assets. */
export async function mergeStaticAssets(
  document: Level3D,
  id: string,
  expectedObstacles: number[],
  inputs: StaticAssetInput[],
) {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(id) || inputs.length < 2)
    throw new Error("A canonical asset ID and at least two assets are required");
  const ids = new Set(inputs.map((input) => input.descriptor.id));
  if (ids.size !== inputs.length || ids.has(id)) throw new Error("Duplicate asset IDs");
  const nodes = new Set<string>();
  const obstacles: number[] = [];
  const selected = inputs.map(({ descriptor }) => {
    assertStaticDescriptor(descriptor);
    const parts = document.objects.filter((part) =>
      part.node.startsWith(`asset:${descriptor.id}:`),
    );
    const groups = new Set(parts.map((part) => part.group));
    const group = document.groups.find((entry) => entry.id === parts[0]?.group);
    if (
      !group ||
      groups.size !== 1 ||
      group.hidden ||
      group.states ||
      group.patches ||
      group.transform.rot_deg !== 0 ||
      parts.length !== descriptor.parts.length ||
      document.objects.some((part) => part.group === group.id && !parts.includes(part))
    )
      throw new Error(`Asset must have one complete static placement: ${descriptor.id}`);
    for (const part of descriptor.parts) {
      const placed = parts.find((entry) => entry.node === assetNodeKey(descriptor.id, part.node));
      if (
        !placed ||
        !isIdentity(placed.transform) ||
        placed.hidden ||
        placed.patches ||
        part.default_hidden ||
        part.source_obstacle === undefined ||
        part.source_components ||
        nodes.has(part.node)
      )
        throw new Error(`Unsupported or duplicate part: ${part.node}`);
      nodes.add(part.node);
      obstacles.push(part.source_obstacle);
    }
    return { group, parts };
  });
  const sorted = (values: number[]) => [...values].sort((a, b) => a - b);
  if (
    new Set(obstacles).size !== obstacles.length ||
    canonical(sorted(obstacles)) !== canonical(sorted(expectedObstacles))
  )
    throw new Error("Catalog membership does not match complete selected assets");
  if (
    document.groups.some((group) => group.id === id) ||
    document.assetSources?.some((source) => source.id === id)
  )
    throw new Error(`Canonical asset already exists: ${id}`);
  const origin = selected[0]!.group.transform;
  const result = structuredClone(document);
  const parts: ProjectionAssetDescriptor["parts"] = [];
  const target = new Document();
  const scene = target.createScene("default");
  target.getRoot().setDefaultScene(scene);
  const expectedNodes: unknown[] = [];
  for (const [i, { descriptor, model }] of inputs.entries()) {
    if (descriptor.source_map !== inputs[0]!.descriptor.source_map)
      throw new Error("Cannot combine unrelated source maps");
    const placement = selected[i]!;
    const delta = {
      dx: placement.group.transform.dx - origin.dx,
      dy: placement.group.transform.dy - origin.dy,
      dz: placement.group.transform.dz - origin.dz,
    };
    const sourceScenes = model.getRoot().listScenes();
    const source = sourceScenes[0];
    if (
      sourceScenes.length !== 1 ||
      !source ||
      (descriptor.model_scene && source.getName() !== descriptor.model_scene) ||
      Object.keys(source.getExtras()).length
    )
      throw new Error(`Expected one static scene without scene metadata: ${descriptor.id}`);
    if (Object.keys(model.getRoot().getExtras()).length)
      throw new Error(`Model requires explicit root metadata migration: ${descriptor.id}`);
    const reachable: string[] = [];
    source.traverse((node) => reachable.push(node.getName()));
    for (const part of descriptor.parts)
      if (reachable.filter((name) => name === part.node).length !== 1)
        throw new Error(`Missing or ambiguous model part: ${part.node}`);
    const wrapper = model
      .createNode(`placement:${descriptor.id}`)
      .setTranslation(sceneToGltf(gameToScene(document.camera, delta.dx, delta.dy, delta.dz)));
    for (const child of source.listChildren()) wrapper.addChild(child);
    source.addChild(wrapper);
    const proof = await modelContentSignatures(model);
    for (const part of descriptor.parts)
      expectedNodes.push(
        proof.nodeData(
          model
            .getRoot()
            .listNodes()
            .find((node) => node.getName() === part.node)!,
        ),
      );
    const mapped = mergeDocuments(target, model);
    const merged = mapped.get(source)!;
    if (!(merged instanceof Scene)) throw new Error("Missing merged scene");
    for (const child of merged.listChildren()) scene.addChild(child);
    merged.dispose();
    for (const part of descriptor.parts) {
      const copy = structuredClone(part);
      if (copy.obstacle_local_game)
        for (const point of copy.obstacle_local_game.points) {
          point.x += delta.dx;
          point.y += delta.dy;
          point.z_bottom += delta.dz;
          point.z_top += delta.dz;
        }
      parts.push(copy);
      const placed = result.objects.find(
        (entry) => entry.node === assetNodeKey(descriptor.id, part.node),
      )!;
      placed.node = assetNodeKey(id, part.node);
      placed.group = id;
      placed.obstacle = copy.obstacle_local_game;
    }
  }
  result.groups = result.groups.filter(
    (group) => !selected.some((entry) => entry.group.id === group.id),
  );
  result.groups.push({ id, transform: { ...origin } });
  for (const { parts: oldParts } of selected)
    for (const old of oldParts) {
      const next = result.objects.find((part) => part.id === old.id)!;
      const before = transformedObstacle(document, old).points;
      const after = transformedObstacle(result, next).points;
      for (const [index, point] of before.entries())
        for (const key of ["x", "y", "z_bottom", "z_top"] as const)
          if (Math.abs(point[key] - after[index]![key]) > 1e-9)
            throw new Error(`World collision geometry changed: ${old.id}`);
    }
  const names = parts.map((part) => part.node);
  await target.transform(unpartition());
  // Embedded output has no external resource names; merged inputs may reuse URI strings.
  for (const texture of target.getRoot().listTextures()) texture.setURI("");
  await normalizeStaticAssetModel(target, id, names);
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  const bytes = await io.writeBinary(target);
  const roundtrip = await io.readBinary(bytes);
  await verifyStaticParts(roundtrip, names, expectedNodes);
  const descriptor: ProjectionAssetDescriptor = {
    version: 1,
    kind: "projection-mapped-asset",
    id,
    name: id,
    source_map: inputs[0]!.descriptor.source_map,
    source_origin_scene: gameToScene(document.camera, origin.dx, origin.dy, origin.dz),
    model: "model.glb",
    model_scene: "default",
    resources: [],
    parts,
  };
  result.assetSources = result.assetSources?.filter((source) => !ids.has(source.id));
  return { document: result, descriptor, bytes };
}
