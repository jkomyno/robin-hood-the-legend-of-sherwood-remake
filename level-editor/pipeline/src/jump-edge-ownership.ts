import type { JumpLine, SightObstacle, Point } from "../../shared/src/level.ts";
import { distanceToPolygon } from "./recovery-elevation.ts";

/** Partitioned assets own only the edges contained by their own projection footprint. */
export function jumpEdgeOwners<T extends { asset: string }>(
  line: JumpLine,
  candidates: T[],
  shape: (owner: T) => SightObstacle,
): T[] {
  const a = line.point_a.slice(0, 2) as Point,
    b = line.point_b.slice(0, 2) as Point;
  const direction: Point = [b[0] - a[0], b[1] - a[1]];
  const cross = (a: Point, b: Point) => a[0] * b[1] - a[1] * b[0];
  return [...new Set(candidates.map((o) => o.asset))].flatMap((asset) => {
    const owners = candidates.filter((o) => o.asset === asset);
    const contours = owners.map((owner) =>
      shape(owner).points.map((p): Point => [p.x, p.y - p.z_top]),
    );
    const covered = (p: Point) => contours.some((c) => distanceToPolygon(p, c) < 1e-7);
    if (!covered(a) || !covered(b)) return [];
    const breaks = [0, 1];
    for (const contour of contours)
      for (let i = 0; i < contour.length; i++) {
        const c = contour[i]!,
          d = contour[(i + 1) % contour.length]!;
        const edge: Point = [d[0] - c[0], d[1] - c[1]],
          offset: Point = [c[0] - a[0], c[1] - a[1]];
        const denominator = cross(direction, edge);
        if (Math.abs(denominator) < 1e-10) continue;
        const t = cross(offset, edge) / denominator,
          u = cross(offset, direction) / denominator;
        if (t > 0 && t < 1 && u >= 0 && u <= 1) breaks.push(t);
      }
    breaks.sort((a, b) => a - b);
    for (let i = 1; i < breaks.length; i++) {
      const t = (breaks[i - 1]! + breaks[i]!) / 2;
      if (!covered([a[0] + t * direction[0], a[1] + t * direction[1]])) return [];
    }
    return owners;
  });
}
