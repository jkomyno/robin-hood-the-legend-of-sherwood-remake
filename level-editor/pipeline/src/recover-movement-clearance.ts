import clipping, { type MultiPolygon } from "polygon-clipping";
import type { SightObstacle, Point } from "@rle/shared";
import { planeHeight, type HeightPlane } from "../../shared/src/gameplay-plane.ts";
import { simplifyMotionRing } from "../../shared/src/motion-quantization.ts";

function removeClippingNoise(regions: MultiPolygon): MultiPolygon {
  // Coincident contacts can leave microscopic rings with no usable height plane.
  // Keep this far below the movement grid so real subpixel openings survive.
  return regions.flatMap((region) => {
    const rings = region.map((ring) => simplifyMotionRing(ring, 1e-8));
    if (rings[0]!.length < 3) return [];
    return [
      [rings[0]!, ...rings.slice(1).filter((ring) => ring.length >= 3)].map((ring) => [
        ...ring,
        ring[0]!,
      ]),
    ];
  });
}

/** Recover only the walkable part of this solid's footprint, in projected coordinates. */
export function recoverMovementClearance(
  free: MultiPolygon,
  plane: HeightPlane,
  solid: SightObstacle,
  roundingMargin = 0,
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
  if (!Number.isFinite(roundingMargin) || roundingMargin < 0)
    throw new Error("Invalid clearance rounding margin");
  if (!roundingMargin)
    return removeClippingNoise(clipping.intersection(free, [[...footprint, footprint[0]!]]));
  // Clearance only subtracts its owner's solid. Extending outside that solid
  // preserves its effect while preventing rounding from shaving thin openings.
  const xs = footprint.map((p) => p[0]),
    ys = footprint.map((p) => p[1]);
  const left = Math.min(...xs) - roundingMargin,
    right = Math.max(...xs) + roundingMargin;
  const top = Math.min(...ys) - roundingMargin,
    bottom = Math.max(...ys) + roundingMargin;
  return removeClippingNoise(
    clipping.intersection(free, [
      [
        [left, top],
        [right, top],
        [right, bottom],
        [left, bottom],
        [left, top],
      ],
    ]),
  );
}
