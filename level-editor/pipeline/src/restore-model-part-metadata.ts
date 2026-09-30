import type { ProjectionAssetDescriptor } from "../../shared/src/projection-assets.ts";

/** Restore absent ownership tags without changing geometry, materials or buffers. */
export function restoreModelPartMetadata(bytes: Uint8Array, descriptor: ProjectionAssetDescriptor) {
  const source = Buffer.from(bytes);
  if (
    source.readUInt32LE(0) !== 0x46546c67 ||
    source.readUInt32LE(4) !== 2 ||
    source.readUInt32LE(8) !== source.length ||
    source.readUInt32LE(16) !== 0x4e4f534a
  )
    throw new Error("Expected GLB 2 JSON chunk");
  const jsonLength = source.readUInt32LE(12);
  const document = JSON.parse(source.subarray(20, 20 + jsonLength).toString()) as {
    nodes?: { name?: string; extras?: Record<string, unknown> }[];
  };
  const restored: string[] = [];
  for (const part of descriptor.parts) {
    const nodes =
      document.nodes?.filter(
        (node) => node.name === part.node && node.extras?.asset_group === undefined,
      ) ?? [];
    if (nodes.length !== 1) throw new Error(`Missing or ambiguous model part: ${part.node}`);
    const node = nodes[0]!;
    for (const key of ["source_obstacle", "source_components"] as const) {
      const expected = part[key];
      if (expected === undefined) continue;
      const existing = node.extras?.[key];
      if (existing !== undefined && JSON.stringify(existing) !== JSON.stringify(expected))
        throw new Error(`Conflicting ${key}: ${part.node}`);
      if (existing === undefined) {
        node.extras = { ...node.extras, [key]: expected };
        restored.push(`${part.node}.${key}`);
      }
    }
  }
  if (!restored.length) return { bytes: source, restored };
  const json = Buffer.from(JSON.stringify(document));
  const padded = Buffer.alloc(Math.ceil(json.length / 4) * 4, 0x20);
  json.copy(padded);
  const header = Buffer.from(source.subarray(0, 20));
  const tail = source.subarray(20 + jsonLength);
  header.writeUInt32LE(20 + padded.length + tail.length, 8);
  header.writeUInt32LE(padded.length, 12);
  return { bytes: Buffer.concat([header, padded, tail]), restored };
}
