import clipping, { type MultiPolygon } from "polygon-clipping";
import type { Point } from "./level.ts";
import { fixedPolygonBoolean } from "./fixed-polygon-boolean.ts";
import { normalizeGeneratedMotion } from "./normalize-generated-motion.ts";
import { simplifyMotionRing, quantizeGeneratedMotionPolygon } from "./motion-quantization.ts";
import { partitionMovementObstacles } from "./partition-movement-obstacles.ts";
import { assembleMovementContour } from "./assemble-movement-contour.ts";

/** Motion obstacles may cross the outer boundary. Keep both contours so their
 * fractional intersection remains implicit in the runtime's containment queries. */
export function preserveMovementBoundary(
  boundary: Point[],
  cutouts: MultiPolygon,
  warnings: string[],
  contourGroups?: (string | undefined)[],
) {
  const quantized = quantizeGeneratedMotionPolygon(
    [boundary],
    Math.round,
    "Preserved movement boundary",
    warnings,
  );
  if (!quantized) throw new Error("Preserved movement boundary collapsed on the movement grid");
  const outer = simplifyMotionRing(quantized[0]!);
  if (contourGroups && contourGroups.length !== cutouts.length)
    throw new Error("Movement contour labels do not match the cutouts");
  const groups = new Map<string | undefined, MultiPolygon>();
  for (const [index, cutout] of cutouts.entries()) {
    const key = contourGroups?.[index];
    const group = groups.get(key) ?? [];
    group.push(cutout);
    groups.set(key, group);
  }
  const blockers: Point[][] = [];
  for (const [label, group] of groups) {
    const blocked = label === undefined ? clipping.union(group) : assembleMovementContour(group);
    // Rounding an outside contact must not manufacture an inward-facing corner.
    // Clean clipping-grid noise only for generated, fractional contours; complete
    // integer contours retain their implicit fractional intersections.
    const overlapping = blocked.filter((region) => {
      const tolerance = region.every((ring) =>
        ring.every(([x, y]) => Number.isInteger(x) && Number.isInteger(y)),
      )
        ? 0
        : 2 / 1048576;
      return clipping
        .intersection([boundary], region)
        .some((overlap) => simplifyMotionRing(overlap[0]!, tolerance).length >= 3);
    });
    for (const region of normalizeGeneratedMotion(
      overlapping,
      "Preserved movement obstacle",
      warnings,
    )) {
      if (!fixedPolygonBoolean("intersection", [outer], [region]).length) continue;
      blockers.push(...partitionMovementObstacles(region));
    }
  }
  return { polygon: outer, blockers };
}
