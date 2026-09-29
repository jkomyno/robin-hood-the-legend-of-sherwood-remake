import earcut, { flatten } from "earcut";
import polygonClipping, { type MultiPolygon } from "polygon-clipping";
import type { NavigationPiece } from "./assemble-navigation-regions.ts";
import type { Point } from "./level.ts";
import type { HeightPlane } from "./gameplay-plane.ts";
import { quantizeGeneratedMotionPolygon, simplifyMotionRing } from "./motion-quantization.ts";
import { preserveMovementBoundary } from "./preserve-movement-boundary.ts";
import { assembleMovementContour } from "./assemble-movement-contour.ts";

export interface PlacedTransitionBlocker {
  transition: string;
  applied: boolean;
  polygon: Point[];
  holes: Point[][];
  plane: HeightPlane;
  movementContour?: string;
}

/** Allocate independent bit pairs per assembled area; no source-map state IDs survive. */
export function compileTransitionObstacles(
  boundary: Point[],
  holes: Point[][],
  plane: HeightPlane,
  blockers: PlacedTransitionBlocker[],
  warnings: string[],
  receivers?: NavigationPiece[],
  preserveBoundary = false,
) {
  if (preserveBoundary && receivers)
    throw new Error("Preserved state contours require one movement boundary");
  const pairs = new Map<string, number>();
  const obstacles: { state_id: number; polygon: { points: Point[] } }[] = [];
  const initial: Point[][] = [];
  // Movement obstacles can cross the area's outer contour.
  const coverage = (polygon: Point[], blockers: Point[][]): MultiPolygon =>
    blockers.length
      ? polygonClipping.difference(
          [polygon],
          blockers.map((b) => [b]),
        )
      : [[polygon]];
  const walkable = blockers.length ? coverage(boundary, holes) : [];
  const groups: {
    transition: string;
    applied: boolean;
    movementContour?: string;
    regions: MultiPolygon;
  }[] = [];
  for (const blocker of blockers) {
    const samePlane = (plane: HeightPlane) =>
      plane.every((n, i) => Math.abs(n - blocker.plane[i]!) < 1e-7);
    if (!receivers && !samePlane(plane)) continue;
    let clipped: MultiPolygon;
    if (receivers) {
      const fragments = receivers
        .filter((r) => samePlane(r.plane))
        .flatMap((r) =>
          polygonClipping.intersection(coverage(r.polygon, r.blockers), walkable, [
            blocker.polygon,
            ...blocker.holes,
          ]),
        );
      clipped = fragments.length ? polygonClipping.union(fragments[0]!, ...fragments.slice(1)) : [];
    } else clipped = polygonClipping.intersection(walkable, [blocker.polygon, ...blocker.holes]);
    // Keep the complete contour after testing overlap. Rounding its clipped
    // intersections would change narrow routes along the movement envelope.
    if (preserveBoundary && clipped.length) clipped = [[blocker.polygon, ...blocker.holes]];
    let group =
      blocker.movementContour === undefined
        ? undefined
        : groups.find(
            (g) =>
              g.transition === blocker.transition &&
              g.applied === blocker.applied &&
              g.movementContour === blocker.movementContour,
          );
    if (!group) {
      group = {
        transition: blocker.transition,
        applied: blocker.applied,
        movementContour: blocker.movementContour,
        regions: [],
      };
      groups.push(group);
    }
    group.regions.push(...clipped);
  }
  for (const blocker of groups) {
    if (!blocker.regions.length) continue;
    let clipped =
      blocker.movementContour === undefined
        ? blocker.regions
        : assembleMovementContour(blocker.regions);
    if (preserveBoundary)
      clipped = preserveMovementBoundary(boundary, clipped, warnings).blockers.map((points) => [
        points,
      ]);
    for (const region of clipped) {
      const rounded = quantizeGeneratedMotionPolygon(
        region,
        Math.round,
        blocker.transition,
        warnings,
      );
      if (!rounded) continue;
      let pair = pairs.get(blocker.transition);
      if (pair === undefined) {
        pair = pairs.size;
        if (pair >= 16)
          throw new Error(
            "More than 16 independent movement transitions affect one navigation area",
          );
        pairs.set(blocker.transition, pair);
      }
      const state_id = (1 << (2 * pair + (blocker.applied ? 1 : 0))) >>> 0;
      const rings = rounded.map((ring) => simplifyMotionRing(ring));
      let pieces: Point[][];
      if (rings.length === 1) pieces = [rings[0]!];
      else {
        const { vertices, holes, dimensions } = flatten(rings);
        const indices = earcut(vertices, holes, dimensions);
        if (!indices.length)
          throw new Error(`${blocker.transition}: failed to triangulate movement blocker holes`);
        pieces = [];
        for (let i = 0; i < indices.length; i += 3)
          pieces.push(
            indices
              .slice(i, i + 3)
              .map((index) => [vertices[index * 2]!, vertices[index * 2 + 1]!]),
          );
      }
      for (const points of pieces) {
        const area = points.reduce((sum, p, i) => {
          const q = points[(i + 1) % points.length]!;
          return sum + p[0] * q[1] - q[0] * p[1];
        }, 0);
        if (points.length < 3 || Math.abs(area) < 1)
          throw new Error(`${blocker.transition}: degenerate state-dependent movement blocker`);
        if (area < 0) points.reverse();
        obstacles.push({ state_id, polygon: { points } });
        if (!blocker.applied) initial.push(points);
      }
    }
  }
  return { pairs, obstacles, initial };
}
