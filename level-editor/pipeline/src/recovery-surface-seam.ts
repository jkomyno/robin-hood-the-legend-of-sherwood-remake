import clipping, { type MultiPolygon, type Polygon } from "polygon-clipping";
import type { Point } from "@rle/shared";
import { clipHeight, planeHeight, type HeightPlane } from "../../shared/src/gameplay-plane.ts";

/** Two complementary mesh pieces can retain a surface's outer boundary by sharing its cut. */
export function recoverSurfaceSeam(
  regions: MultiPolygon,
  footprints: Polygon[],
): MultiPolygon[] | undefined {
  if (regions.length !== 1 || footprints.length !== 2 || footprints.some((p) => p.length !== 1))
    return undefined;
  const [first, second] = footprints.map((p) => p[0]!);
  if (!first?.length || !second?.length) return undefined;
  const epsilon = 0.001;
  const cuts: HeightPlane[] = [];
  for (let i = 0; i < first.length; i++) {
    const a = first[i]!,
      b = first[(i + 1) % first.length]!;
    const dx = b[0] - a[0],
      dy = b[1] - a[1],
      length = Math.hypot(dx, dy);
    if (length <= epsilon) continue;
    let plane: HeightPlane = [-dy / length, dx / length, (dy * a[0] - dx * a[1]) / length];
    const values = first.map((p) => planeHeight(plane, p));
    if (Math.max(...values) - Math.min(...values) <= epsilon) continue;
    if (Math.min(...values) < -epsilon && Math.max(...values) > epsilon) continue;
    if (Math.max(...values) <= epsilon) plane = plane.map((n) => -n) as HeightPlane;
    const opposite = second.map((p) => planeHeight(plane, p));
    if (Math.max(...opposite) > epsilon || Math.min(...opposite) >= -epsilon) continue;
    const along = (p: Point) => ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length;
    const sharedEdge = second.some((c, j) => {
      const d = second[(j + 1) % second.length]!;
      if (Math.abs(planeHeight(plane, c)) > epsilon || Math.abs(planeHeight(plane, d)) > epsilon)
        return false;
      return (
        Math.min(length, Math.max(along(c), along(d))) - Math.max(0, Math.min(along(c), along(d))) >
        1
      );
    });
    if (sharedEdge && !cuts.some((p) => p.every((v, k) => Math.abs(v - plane[k]!) < 1e-5)))
      cuts.push(plane);
  }
  if (cuts.length !== 1) return undefined;
  const points = regions.flat(2);
  const xs = points.map((p) => p[0]),
    ys = points.map((p) => p[1]);
  const left = Math.min(...xs) - 1,
    right = Math.max(...xs) + 1,
    top = Math.min(...ys) - 1,
    bottom = Math.max(...ys) + 1;
  const bounds: Point[] = [
    [left, top],
    [right, top],
    [right, bottom],
    [left, bottom],
  ];
  const owned = [cuts[0]!, cuts[0]!.map((n) => -n) as HeightPlane].map((plane) => {
    const half = clipHeight(bounds, plane);
    return half.length >= 3 ? clipping.intersection(regions, [half]) : [];
  });
  return owned.every((part) => part.length) ? owned : undefined;
}
