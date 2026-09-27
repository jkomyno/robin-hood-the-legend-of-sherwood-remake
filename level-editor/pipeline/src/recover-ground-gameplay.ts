import type { MultiPolygon, Polygon } from "polygon-clipping";
import {
  recoveryClipping as clipping,
  recoveryPolygonBoolean,
} from "./recovery-polygon-boolean.ts";
import type { Point } from "@rle/shared";
import { quantizeRecoveredMotion } from "./quantize-recovered-motion.ts";

export const closedPolygon = (points: Point[]): Polygon => [[...points, points[0]!]];
export function polygonArea(regions: MultiPolygon): number {
  const ringArea = (ring: Point[]) =>
    Math.abs(
      ring.reduce((sum, a, i) => {
        const b = ring[(i + 1) % ring.length]!;
        return sum + a[0] * b[1] - b[0] * a[1];
      }, 0),
    ) / 2;
  return regions.reduce(
    (sum, polygon) =>
      sum +
      ringArea(polygon[0]!) -
      polygon.slice(1).reduce((holes, ring) => holes + ringArea(ring), 0),
    0,
  );
}

/** Offline recovery: fill placed-object cutouts in terrain and move them to their owners. */
export function recoverGroundGameplay(
  areas: { polygon: { points: Point[] }; obstacles: { polygon: { points: Point[] } }[] }[],
  owners: { asset: string; node: string; footprint: Point[] }[],
) {
  if (!areas.length) throw new Error("No authored ground movement regions");
  const warnings: string[] = [];
  const normalize = (regions: MultiPolygon, label: string) =>
    quantizeRecoveredMotion(regions, label, warnings, (rounded) =>
      recoveryPolygonBoolean("union", rounded, [], 1),
    );
  const free = areas.flatMap((area) => {
    const boundary = closedPolygon(area.polygon.points);
    const holes = area.obstacles.map((o) => closedPolygon(o.polygon.points));
    return holes.length ? clipping.difference(boundary, ...holes) : [boundary];
  });
  if (!free.length) throw new Error("Ground movement regions contain no walkable space");
  const walkable = clipping.union(free[0]!, ...free.slice(1));
  const boundaries = areas.map((area) => closedPolygon(area.polygon.points));
  const envelope = clipping.union(boundaries[0]!, ...boundaries.slice(1));
  // Only recover the excluded portion of an asset footprint. Sight geometry
  // and movement contours are not interchangeable: replacing one with the
  // other would change clearances even at the unchanged placement.
  const blockers = owners.flatMap((owner) => {
    // Disconnected ground sectors must not claim unrelated assets elsewhere on the map.
    if (!clipping.intersection(closedPolygon(owner.footprint), envelope).length) return [];
    const regions = normalize(
      clipping.difference(closedPolygon(owner.footprint), walkable),
      `${owner.asset}/${owner.node} ground blocker`,
    );
    return regions.length ? [{ asset: owner.asset, node: owner.node, regions }] : [];
  });
  const additions = blockers.flatMap((b) => b.regions);
  const excluded = additions.length ? clipping.union(additions[0]!, ...additions.slice(1)) : [];
  // A placed footprint can cross the authored outer boundary. It may own an
  // exclusion there, but must not extend the terrain beyond that boundary.
  // Fill owned exclusions by subtracting the remaining holes from the envelope.
  // This avoids rejoining coincident fractional boundaries before clipping them.
  const holes = clipping.difference(envelope, walkable);
  const remaining = excluded.length ? clipping.difference(holes, excluded) : holes;
  const terrain = normalize(
    remaining.length ? clipping.difference(envelope, remaining) : envelope,
    "Recovered ground",
  );
  const reconstructed = excluded.length ? clipping.difference(terrain, excluded) : terrain;
  const difference = clipping.xor(walkable, reconstructed);
  return {
    terrain,
    blockers,
    warnings,
    coordinateGrid: 1,
    sourceArea: polygonArea(walkable),
    reconstructedArea: polygonArea(reconstructed),
    differenceArea: polygonArea(difference),
  };
}
