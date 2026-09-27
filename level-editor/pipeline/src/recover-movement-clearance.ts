import clipping, { type MultiPolygon } from "polygon-clipping";
import type { SightObstacle, Point } from "@rle/shared";
import { planeHeight, type HeightPlane } from "../../shared/src/gameplay-plane.ts";

/** Recover only the walkable part of this solid's footprint, in projected coordinates. */
export function recoverMovementClearance(
  free: MultiPolygon,
  plane: HeightPlane,
  solid: SightObstacle,
): MultiPolygon {
  if (!solid.solid || !free.length) return [];
  const denominator = 1 + plane[1];
  if (Math.abs(denominator) < 1e-8)
    throw new Error("Movement clearance needs a nonvertical world surface");
  const footprint = solid.points.map((p): Point => [
    p.x,
    (p.y - plane[0] * p.x - plane[2]) / denominator,
  ]);
  const heights = footprint.map((p) => planeHeight(plane, p));
  if (
    Math.max(...solid.points.map((p) => p.z_top)) <= Math.min(...heights) + 1e-7 ||
    Math.min(...solid.points.map((p) => p.z_bottom)) > Math.max(...heights) + 1e-7
  )
    return [];
  return clipping.intersection(free, [[...footprint, footprint[0]!]]);
}
