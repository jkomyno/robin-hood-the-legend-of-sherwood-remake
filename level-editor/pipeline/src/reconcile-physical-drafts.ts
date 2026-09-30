import { isDeepStrictEqual } from "node:util";
import { mat4 } from "gl-matrix";
import type { GameplayAssetDescriptor } from "../../shared/src/asset-gameplay.ts";
import { parseProjectionAssetDescriptor } from "../../shared/src/validation.ts";
import { mergeGameplayDraft } from "./publish-gameplay-drafts.ts";

export const REVIEWED_PHYSICAL_FIELDS = new Set([
  "obstacle_local_game",
  "collision",
  "sight_join_edges",
  "sight_join_caps",
]);

export function verifyPhysicalPartIdentity(
  live: Record<string, unknown>[],
  draft: Record<string, unknown>[],
) {
  const identity = (part: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(part).filter(([key]) => !REVIEWED_PHYSICAL_FIELDS.has(key)));
  if (!isDeepStrictEqual(live.map(identity), draft.map(identity)))
    throw new Error("Physical reconciliation changes part identity or authoring metadata");
}

/** Explicit recovery operation; rendering and part identity stay owned by the live asset. */
export function reconcilePhysicalDraft(
  live: GameplayAssetDescriptor,
  draft: GameplayAssetDescriptor,
  issues: string[],
) {
  const identity = (part: GameplayAssetDescriptor["parts"][number]) =>
    Object.fromEntries(Object.entries(part).filter(([key]) => !REVIEWED_PHYSICAL_FIELDS.has(key)));
  if (
    live.id !== draft.id ||
    live.source_map !== draft.source_map ||
    !isDeepStrictEqual(live.source_origin_scene, draft.source_origin_scene) ||
    !isDeepStrictEqual(live.parts.map(identity), draft.parts.map(identity))
  )
    throw new Error(`${live.id}: physical reconciliation changes part identity or frame`);
  const corrected = parseProjectionAssetDescriptor({ ...live, parts: draft.parts });
  return mergeGameplayDraft(corrected, draft, issues);
}

interface GltfNode {
  name?: string;
  children?: number[];
  matrix?: number[];
  translation?: [number, number, number];
  rotation?: [number, number, number, number];
  scale?: [number, number, number];
  extras?: Record<string, unknown>;
}
interface GltfFrames {
  scene?: number;
  scenes?: { name?: string; nodes?: number[] }[];
  nodes?: GltfNode[];
}

/** Inspect canonical part frames without requiring identical refined render meshes. */
export function physicalModelFrames(bytes: Buffer, descriptor: GameplayAssetDescriptor) {
  if (
    bytes.length < 20 ||
    bytes.readUInt32LE(0) !== 0x46546c67 ||
    bytes.readUInt32LE(16) !== 0x4e4f534a
  )
    throw new Error(`${descriptor.id}: invalid GLB frame source`);
  const gltf = JSON.parse(bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString()) as GltfFrames;
  const scenes = descriptor.model_scene
    ? gltf.scenes?.filter((s) => s.name === descriptor.model_scene)
    : [gltf.scenes?.[gltf.scene ?? 0]];
  if (scenes?.length !== 1 || !scenes[0]) throw new Error(`${descriptor.id}: missing model scene`);
  const frames = new Map<string, { matrix: number[]; source: Record<string, unknown> }[]>();
  const visiting = new Set<number>();
  const walk = (index: number, parent: mat4) => {
    const node = gltf.nodes?.[index];
    if (!node || visiting.has(index)) throw new Error(`${descriptor.id}: invalid model hierarchy`);
    visiting.add(index);
    const local = node.matrix
      ? mat4.clone(node.matrix)
      : mat4.fromRotationTranslationScale(
          mat4.create(),
          node.rotation ?? [0, 0, 0, 1],
          node.translation ?? [0, 0, 0],
          node.scale ?? [1, 1, 1],
        );
    const world = mat4.multiply(mat4.create(), parent, local);
    if (node.name) {
      const source = Object.fromEntries(
        Object.entries(node.extras ?? {}).filter(([key]) =>
          ["source_obstacle", "source_node", "source_components", "editor_part_node"].includes(key),
        ),
      );
      const entries = frames.get(node.name) ?? [];
      entries.push({ matrix: Array.from(world), source });
      frames.set(node.name, entries);
    }
    for (const child of node.children ?? []) walk(child, world);
    visiting.delete(index);
  };
  for (const root of scenes[0].nodes ?? []) walk(root, mat4.create());
  return descriptor.parts.map((part) => {
    const found = frames.get(part.node);
    if (found?.length !== 1)
      throw new Error(`${descriptor.id}: missing or ambiguous model frame ${part.node}`);
    const frame = found[0]!;
    if (
      frame.source.source_obstacle !== undefined &&
      frame.source.source_obstacle !== part.source_obstacle
    )
      throw new Error(`${descriptor.id}: model source obstacle mismatch ${part.node}`);
    return { node: part.node, ...frame };
  });
}

export function verifyPhysicalModelFrames(
  live: Buffer,
  liveDescriptor: GameplayAssetDescriptor,
  draft: Buffer,
  draftDescriptor: GameplayAssetDescriptor,
) {
  const before = physicalModelFrames(live, liveDescriptor),
    after = physicalModelFrames(draft, draftDescriptor);
  if (!isDeepStrictEqual(before, after))
    throw new Error(`${liveDescriptor.id}: model part frames or source metadata differ`);
  return before.length;
}
