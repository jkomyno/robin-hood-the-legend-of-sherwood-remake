import { Node, NodeIO, getBounds } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { cloneDocument, unpartition } from "@gltf-transform/functions";
import { assetNodeKey, isIdentity, type Level3D } from "@rle/shared";
import { canonical, modelContentSignatures } from "./bundle-asset-states.ts";
import { assertStaticDescriptor, type StaticAssetInput } from "./merge-static-assets.ts";
import {
  normalizeStaticAssetModel,
  verifyStaticParts,
  writeStaticAssetModel,
} from "./static-asset-model.ts";
import {
  readStaticAssetMetadata,
  splitStaticAssetMetadata,
  staticMetadataKeys,
} from "./static-asset-metadata.ts";

/** Split complete owned subtrees, preserving world geometry in normalized editor frames. */
export async function splitStaticAsset(
  document: Level3D,
  input: StaticAssetInput,
  partitions: { id: string; obstacles: number[] }[],
) {
  const { descriptor, model } = input;
  assertStaticDescriptor(descriptor, staticMetadataKeys);
  const metadata = readStaticAssetMetadata(descriptor);
  const ids = new Set(partitions.map((partition) => partition.id));
  if (
    partitions.length < 2 ||
    ids.size !== partitions.length ||
    partitions.some(
      (partition) => !/^[a-z0-9][a-z0-9-]*$/.test(partition.id) || !partition.obstacles.length,
    ) ||
    document.assetSources?.some((source) => ids.has(source.id)) ||
    document.groups.some((group) => ids.has(group.id))
  )
    throw new Error("Expected distinct new partition IDs and nonempty partitions");
  const sorted = (values: number[]) => [...values].sort((a, b) => a - b);
  const expected = descriptor.parts.map((part) => {
    if (part.source_obstacle === undefined || part.source_components || part.default_hidden)
      throw new Error(`Unsupported split part: ${part.node}`);
    return part.source_obstacle;
  });
  const assigned = partitions.flatMap((partition) => partition.obstacles);
  if (
    new Set(assigned).size !== assigned.length ||
    canonical(sorted(expected)) !== canonical(sorted(assigned))
  )
    throw new Error("Partitions must assign every part exactly once");
  const placed = document.objects.filter((part) => part.node.startsWith(`asset:${descriptor.id}:`));
  const group = document.groups.find((entry) => entry.id === placed[0]?.group);
  if (
    !group ||
    group.transform.rot_deg !== 0 ||
    group.hidden ||
    group.states ||
    group.patches ||
    placed.length !== descriptor.parts.length ||
    placed.some(
      (part) =>
        part.group !== group.id || !isIdentity(part.transform) || part.hidden || part.patches,
    ) ||
    document.objects.some((part) => part.group === group.id && !placed.includes(part))
  )
    throw new Error("Split requires one complete unedited static placement");
  const scenes = model.getRoot().listScenes();
  const scene = scenes[0];
  if (
    !scene ||
    scenes.length !== 1 ||
    Object.keys(scene.getExtras()).length ||
    Object.keys(model.getRoot().getExtras()).length ||
    (descriptor.model_scene && descriptor.model_scene !== scene.getName())
  )
    throw new Error("Split requires one scene without root or scene metadata");
  const reachable: Node[] = [];
  scene.traverse((node) => reachable.push(node));
  const partNames = new Set(descriptor.parts.map((part) => part.node));
  const owned = new Set<Node>();
  for (const node of reachable)
    if (partNames.has(node.getName())) node.traverse((child) => owned.add(child));
  if (
    partNames.size !== descriptor.parts.length ||
    reachable.some((node) => (node.getMesh() && !owned.has(node)) || node.getCamera())
  )
    throw new Error("Split requires every rendered node to be an owned part");
  for (const part of descriptor.parts) {
    const matches = reachable.filter((node) => node.getName() === part.node);
    if (
      matches.length !== 1 ||
      placed.filter((entry) => entry.node === assetNodeKey(descriptor.id, part.node)).length !== 1
    )
      throw new Error(`Split requires unique parts: ${part.node}`);
    for (let parent = matches[0]!.getParentNode(); parent; parent = parent.getParentNode())
      if (partNames.has(parent.getName()))
        throw new Error(`Split cannot partition nested owned parts: ${part.node}`);
  }
  const proof = await modelContentSignatures(model);
  const result = structuredClone(document);
  result.groups = result.groups.filter((entry) => entry.id !== group.id);
  result.assetSources = result.assetSources?.filter((source) => source.id !== descriptor.id);
  const outputs = [];
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  for (const partition of partitions) {
    const parts = descriptor.parts.filter((part) =>
      partition.obstacles.includes(part.source_obstacle!),
    );
    const names = new Set(parts.map((part) => part.node));
    const copy = cloneDocument(model);
    const keep = new Set<Node>();
    for (const node of copy.getRoot().listNodes())
      if (names.has(node.getName())) {
        node.traverse((child) => keep.add(child));
        let ancestor: Node | null = node;
        while (ancestor) {
          keep.add(ancestor);
          ancestor = ancestor.getParentNode();
        }
      }
    for (const node of copy.getRoot().listNodes()) if (!keep.has(node)) node.dispose();
    await normalizeStaticAssetModel(copy, partition.id, [...names]);
    await copy.transform(unpartition());
    const bytes = await writeStaticAssetModel(io, copy);
    const roundtrip = await io.readBinary(bytes);
    await verifyStaticParts(
      roundtrip,
      [...names],
      [...names].map((name) => proof.nodeData(reachable.find((node) => node.getName() === name)!)),
    );
    const bounds = getBounds(roundtrip.getRoot().listScenes()[0]!);
    const next = {
      ...structuredClone(descriptor),
      ...splitStaticAssetMetadata(metadata, names, {
        min: [bounds.min[0], -bounds.max[2], bounds.min[1]],
        max: [bounds.max[0], -bounds.min[2], bounds.max[1]],
      }),
      id: partition.id,
      name: partition.id,
      model: "model.glb",
      model_scene: scene.getName(),
      resources: [],
      parts: structuredClone(parts),
    };
    result.groups.push({ ...structuredClone(group), id: partition.id });
    for (const part of parts) {
      const instance = result.objects.find(
        (entry) => entry.node === assetNodeKey(descriptor.id, part.node),
      )!;
      instance.group = partition.id;
      instance.node = assetNodeKey(partition.id, part.node);
    }
    outputs.push({ descriptor: next, model: roundtrip, bytes });
  }
  return { document: result, outputs };
}
