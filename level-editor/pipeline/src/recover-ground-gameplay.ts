import type { MultiPolygon, Polygon } from "polygon-clipping";
import { recoveryClipping as clipping } from "./recovery-polygon-boolean.ts";
import type { Point } from "@rle/shared";
import { simplifyMotionRing } from "../../shared/src/motion-quantization.ts";

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
  preserveBoundary = false,
) {
  if (!areas.length) throw new Error("No authored ground movement regions");
  const warnings: string[] = [];
  const clean = (regions: MultiPolygon): MultiPolygon =>
    regions.flatMap((region) => {
      const rings = region.map((ring) => simplifyMotionRing(ring, 2 / 1048576));
      if (rings[0]!.length < 3) return [];
      return [rings.filter((ring) => ring.length >= 3).map((ring) => [...ring, ring[0]!])];
    });
  const areaFree = areas.map((area) => {
    const boundary = closedPolygon(area.polygon.points);
    const holes = area.obstacles.map((o) => closedPolygon(o.polygon.points));
    return holes.length ? clipping.difference(boundary, ...holes) : [boundary];
  });
  const free = areaFree.flat();
  if (!free.length) throw new Error("Ground movement regions contain no walkable space");
  const walkable = clipping.union(free[0]!, ...free.slice(1));
  const boundaries = areas.map((area) => closedPolygon(area.polygon.points));
  const envelope = clipping.union(boundaries[0]!, ...boundaries.slice(1));
  const authoredExclusions = areas.flatMap((area) =>
    area.obstacles.map((o) => closedPolygon(o.polygon.points)),
  );
  const excludedCoverage = authoredExclusions.length
    ? clipping.difference(
        clipping.union(authoredExclusions[0]!, ...authoredExclusions.slice(1)),
        walkable,
      )
    : [];
  // Only recover the excluded portion of an asset footprint. Sight geometry
  // and movement contours are not interchangeable: replacing one with the
  // other would change clearances even at the unchanged placement.
  const blockers = owners.flatMap((owner) => {
    // Disconnected ground sectors must not claim unrelated assets elsewhere on the map.
    if (!clipping.intersection(closedPolygon(owner.footprint), envelope).length) return [];
    const regions = clean(
      preserveBoundary
        ? clipping.intersection(closedPolygon(owner.footprint), excludedCoverage)
        : clipping.difference(closedPolygon(owner.footprint), walkable),
    );
    return regions.length ? [{ asset: owner.asset, node: owner.node, regions }] : [];
  });
  const additions = blockers.flatMap((b) => b.regions);
  const excluded = additions.length ? clipping.union(additions[0]!, ...additions.slice(1)) : [];
  // A placed footprint can cross the authored outer boundary. It may own an
  // exclusion there, but must not extend the terrain beyond that boundary.
  // Fill owned exclusions by subtracting the remaining holes from the envelope.
  // This avoids rejoining coincident fractional boundaries before clipping them.
  const sections = areas.map((area, index) => {
    const boundary = closedPolygon(area.polygon.points);
    // Keep the authored exclusions. Reconstructing their complement from an
    // already clipped free-space polygon can erase narrow corridors at shared edges.
    const authoredHoles = area.obstacles.map((obstacle) => closedPolygon(obstacle.polygon.points));
    const holes = authoredHoles.length
      ? clipping.intersection(
          boundary,
          clipping.union(authoredHoles[0]!, ...authoredHoles.slice(1)),
        )
      : [];
    const remaining = excluded.length ? clipping.difference(holes, excluded) : holes;
    const completeHoles = authoredHoles.length
      ? clipping.union(authoredHoles[0]!, ...authoredHoles.slice(1))
      : [];
    const movementObstacles = clean(
      excluded.length ? clipping.difference(completeHoles, excluded) : completeHoles,
    );
    const terrain = clean(remaining.length ? clipping.difference(boundary, remaining) : [boundary]);
    const reconstructed = excluded.length ? clipping.difference(terrain, excluded) : terrain;
    return {
      navigationRegion: `ground-section-${index}`,
      movementBoundary: area.polygon.points,
      movementObstacles,
      terrain,
      differenceArea: polygonArea(clipping.xor(areaFree[index]!, reconstructed)),
    };
  });
  const terrain = sections.flatMap((section) => section.terrain);
  const reconstructed = excluded.length ? clipping.difference(terrain, excluded) : terrain;
  const difference = clipping.xor(walkable, reconstructed);
  return {
    terrain,
    sections,
    blockers,
    warnings,
    coordinateGrid: 1 / 1048576,
    sourceArea: polygonArea(walkable),
    reconstructedArea: polygonArea(reconstructed),
    differenceArea: polygonArea(difference),
  };
}
