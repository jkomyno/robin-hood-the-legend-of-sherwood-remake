import type { Point } from "@rle/shared";

/** Resolve a movement area's projection at the endpoint; uncovered ground is height zero. */
export function recoverEndpointElevation(
  candidates: { distance: number; height: number; maximumHeight: number }[],
  groundLayer: boolean,
): number {
  if (candidates.some((c) => ![c.distance, c.height, c.maximumHeight].every(Number.isFinite)))
    throw new Error("Invalid endpoint projection geometry");
  const containing = candidates.filter((candidate) => candidate.distance === 0);
  if (!containing.length) {
    if (groundLayer) return 0;
    throw new Error("No projection surface for endpoint elevation");
  }
  // Keep source order when bounding heights tie. Priority uses the whole
  // obstacle's maximum height, not its evaluated height at this endpoint.
  return containing.reduce((best, candidate) =>
    candidate.maximumHeight > best.maximumHeight ? candidate : best,
  ).height;
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
