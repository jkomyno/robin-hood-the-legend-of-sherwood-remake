import { isDeepStrictEqual } from "node:util";
import type { LightSector } from "../../shared/src/level.ts";

export interface LightOwnerDeclaration {
  source: number;
  owner: string;
  node: string;
  reason: string;
  light: LightSector;
}

/** Validate one-time lighting ownership against the complete source and placed frame. */
export function declaredLightOwners<T>(
  entries: LightOwnerDeclaration[],
  sources: LightSector[],
  frames: (asset: string, node: string) => T[],
): Map<number, { asset: string; node: string; part: T }> {
  const result = new Map<number, { asset: string; node: string; part: T }>();
  for (const entry of entries) {
    if (
      !Number.isInteger(entry.source) ||
      entry.source < 0 ||
      !sources[entry.source] ||
      result.has(entry.source) ||
      !entry.owner.trim() ||
      !entry.node.trim() ||
      !entry.reason.trim()
    )
      throw new Error("Light ownership needs one source and a reviewed asset frame");
    if (!isDeepStrictEqual(sources[entry.source], entry.light))
      throw new Error(`Light ownership source changed: ${entry.source}`);
    const matches = frames(entry.owner, entry.node);
    if (matches.length !== 1)
      throw new Error(`Light ownership needs one pinned frame: ${entry.owner}:${entry.node}`);
    result.set(entry.source, { asset: entry.owner, node: entry.node, part: matches[0]! });
  }
  return result;
}
