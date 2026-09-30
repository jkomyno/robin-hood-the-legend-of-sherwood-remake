import type { ProtoLevel, Vec3 } from "@rle/shared";
import { heightPlane, type HeightPlane } from "../../shared/src/gameplay-plane.ts";

export interface ReviewedTransitionPlanes {
  source_sha256: string;
  entries: { patch: number; receiver: number }[];
}

/** Authoring-only plane extensions; returned planes never alter receiving coverage. */
export function reviewedTransitionPlanes(
  source: {
    patches: Record<string, unknown>[];
    sight_obstacles: ProtoLevel["sight_obstacles"];
  },
  sourceSha256: string,
  definitions: ReviewedTransitionPlanes,
): Map<number, HeightPlane> {
  if (definitions.source_sha256 !== sourceSha256)
    throw new Error("Transition plane source changed");
  if (!Array.isArray(definitions.entries) || !definitions.entries.length)
    throw new Error("Transition planes need reviewed entries");
  const planes = new Map<number, HeightPlane>();
  for (const entry of definitions.entries) {
    const patch = source.patches[entry.patch],
      receiver = source.sight_obstacles[entry.receiver];
    if (
      !Number.isInteger(entry.patch) ||
      entry.patch < 0 ||
      !Number.isInteger(entry.receiver) ||
      entry.receiver < 0 ||
      planes.has(entry.patch) ||
      !patch ||
      !receiver ||
      !Array.isArray(receiver.projection_area) ||
      receiver.projection_area[0] !== patch.pathfinder_sector ||
      receiver.projection_area[1] !== patch.pathfinder_layer
    )
      throw new Error("Transition plane needs a unique patch and associated receiver");
    planes.set(
      entry.patch,
      heightPlane(receiver.points.slice(0, 3).map((p): Vec3 => [p.x, p.y - p.z_top, p.z_top])),
    );
  }
  return planes;
}
