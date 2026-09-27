import clipping, { type MultiPolygon, type Polygon } from "polygon-clipping";
import type { Point } from "@rle/shared";

export const closedPolygon = (points: Point[]): Polygon => [[...points, points[0]!]];
// Motion coordinates are integer pixels in the engine. Snap intermediate cuts
// to that same grid and report the resulting geometric error explicitly.
const motionGrid = (regions: MultiPolygon): MultiPolygon =>
  regions.flatMap((polygon) => {
    const rings = polygon.map((ring) => {
      const points = ring.map(([x, y]): Point => [Math.round(x), Math.round(y)]);
      const distinct = points.filter((p, i) => {
        const next = points[(i + 1) % points.length]!;
        return p[0] !== next[0] || p[1] !== next[1];
      });
      return distinct.length >= 3 ? [...distinct, distinct[0]!] : [];
    });
    if (!rings[0]!.length || polygonArea([[rings[0]!]]) < 0.5) return [];
    return [[rings[0]!, ...rings.slice(1).filter((r) => r.length && polygonArea([[r]]) >= 0.5)]];
  });
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
    const regions = motionGrid(clipping.difference(closedPolygon(owner.footprint), walkable));
    return regions.length ? [{ asset: owner.asset, node: owner.node, regions }] : [];
  });
  const additions = blockers.flatMap((b) => b.regions);
  const excluded = additions.length ? clipping.union(additions[0]!, ...additions.slice(1)) : [];
  // A placed footprint can cross the authored outer boundary. It may own an
  // exclusion there, but must not extend the terrain beyond that boundary.
  const terrain = excluded.length
    ? motionGrid(clipping.intersection(clipping.union(walkable, excluded), envelope))
    : walkable;
  const reconstructed = excluded.length ? clipping.difference(terrain, excluded) : terrain;
  const difference = clipping.xor(walkable, reconstructed);
  return {
    terrain,
    blockers,
    coordinateGrid: 1,
    sourceArea: polygonArea(walkable),
    reconstructedArea: polygonArea(reconstructed),
    differenceArea: polygonArea(difference),
  };
}
