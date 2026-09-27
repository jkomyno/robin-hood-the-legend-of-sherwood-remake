import earcut, { flatten } from "earcut";
import polygonClipping from "polygon-clipping";
import type { Point } from "./level.ts";
import type { HeightPlane } from "./gameplay-plane.ts";
import { quantizeGeneratedMotionPolygon, simplifyMotionRing } from "./motion-quantization.ts";

export interface PlacedTransitionBlocker {
  transition: string;
  applied: boolean;
  polygon: Point[];
  holes: Point[][];
  plane: HeightPlane;
}

/** Allocate independent bit pairs per assembled area; no source-map state IDs survive. */
export function compileTransitionObstacles(
  boundary: Point[],
  holes: Point[][],
  plane: HeightPlane,
  blockers: PlacedTransitionBlocker[],
  warnings: string[],
) {
  const pairs = new Map<string, number>();
  const obstacles: { state_id: number; polygon: { points: Point[] } }[] = [];
  const initial: Point[][] = [];
  for (const blocker of blockers) {
    if (!plane.every((n, i) => Math.abs(n - blocker.plane[i]!) < 1e-7)) continue;
    const clipped = polygonClipping.intersection(
      [boundary, ...holes],
      [blocker.polygon, ...blocker.holes],
    );
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
      const rings = rounded.map(simplifyMotionRing);
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
