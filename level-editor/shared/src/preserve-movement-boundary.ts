import type { MultiPolygon } from "polygon-clipping";
import type { Point } from "./level.ts";
import { fixedPolygonBoolean } from "./fixed-polygon-boolean.ts";
import { normalizeGeneratedMotion } from "./normalize-generated-motion.ts";
import { simplifyMotionRing, quantizeGeneratedMotionPolygon } from "./motion-quantization.ts";
import { partitionMovementObstacles } from "./partition-movement-obstacles.ts";

/** Motion obstacles may cross the outer boundary. Keep both contours so their
 * fractional intersection remains implicit in the runtime's containment queries. */
export function preserveMovementBoundary(
  boundary: Point[],
  cutouts: MultiPolygon,
  warnings: string[],
) {
  const quantized = quantizeGeneratedMotionPolygon(
    [boundary],
    Math.round,
    "Preserved movement boundary",
    warnings,
  );
  if (!quantized) throw new Error("Preserved movement boundary collapsed on the movement grid");
  const outer = simplifyMotionRing(quantized[0]!);
  const blocked = cutouts.length ? fixedPolygonBoolean("union", cutouts) : [];
  const blockers: Point[][] = [];
  for (const region of normalizeGeneratedMotion(blocked, "Preserved movement obstacle", warnings)) {
    if (!fixedPolygonBoolean("intersection", [outer], [region]).length) continue;
    blockers.push(...partitionMovementObstacles(region));
  }
  return { polygon: outer, blockers };
}
