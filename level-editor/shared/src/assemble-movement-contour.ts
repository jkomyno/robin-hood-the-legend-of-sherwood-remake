import clipping, { type MultiPolygon } from "polygon-clipping";
import type { Point } from "./level.ts";

/** Rejoin fragments despite two clipping-grid units per axis of endpoint noise. */
export function assembleMovementContour(fragments: MultiPolygon): MultiPolygon {
  const points = fragments.flat(2);
  const scale = points.reduce((max, [x, y]) => Math.max(max, Math.abs(x), Math.abs(y)), 1);
  // Use a rotation-invariant distance bound for nearby endpoints.
  // Anchors never move, preventing transitive drift.
  const tolerance = (2 * Math.SQRT2) / 1048576 + 8 * Number.EPSILON * scale;
  const buckets = new Map<string, Point[]>();
  const replacements = new Map<Point, Point>();
  for (const point of [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1])) {
    const bx = Math.floor(point[0] / tolerance),
      by = Math.floor(point[1] / tolerance);
    let match: Point | undefined;
    let distance = Infinity;
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++) {
        for (const candidate of buckets.get(`${bx + dx}:${by + dy}`) ?? []) {
          const x = Math.abs(point[0] - candidate[0]),
            y = Math.abs(point[1] - candidate[1]);
          if (x * x + y * y <= tolerance * tolerance && x * x + y * y < distance) {
            match = candidate;
            distance = x * x + y * y;
          }
        }
      }
    if (!match) {
      match = point;
      const key = `${bx}:${by}`;
      const bucket = buckets.get(key) ?? [];
      bucket.push(point);
      buckets.set(key, bucket);
    }
    replacements.set(point, match);
  }
  return clipping.union(
    fragments.map((polygon) =>
      polygon.map((ring) => ring.map((point) => replacements.get(point)!)),
    ),
  );
}
