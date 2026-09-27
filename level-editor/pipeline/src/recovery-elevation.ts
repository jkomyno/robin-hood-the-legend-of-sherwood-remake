import type { Point } from "@rle/shared";

/** Choose among surfaces in one movement area without extrapolating the first surface arbitrarily. */
export function recoverEndpointElevation(
  candidates: { distance: number; height: number }[],
  groundLayer: boolean,
): number {
  const containing = candidates.filter((candidate) => candidate.distance < 1);
  const selected = containing.length ? containing : candidates;
  if (!selected.length) {
    if (groundLayer) return 0;
    throw new Error("No projection surface for endpoint elevation");
  }
  const heights = selected.map((candidate) => candidate.height);
  if (!heights.every(Number.isFinite) || Math.max(...heights) - Math.min(...heights) > 0.01)
    throw new Error("Ambiguous endpoint elevation across projection surfaces");
  return heights[0]!;
}

export function distanceToPolygon(point: Point, points: Point[]): number {
  let inside = false,
    distance = Infinity;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const a = points[i]!,
      b = points[j]!;
    const dx = b[0] - a[0],
      dy = b[1] - a[1];
    if (
      a[1] > point[1] !== b[1] > point[1] &&
      point[0] < ((b[0] - a[0]) * (point[1] - a[1])) / (b[1] - a[1]) + a[0]
    )
      inside = !inside;
    const t = Math.max(
      0,
      Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy || 1)),
    );
    distance = Math.min(distance, Math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy));
  }
  return inside ? 0 : distance;
}
