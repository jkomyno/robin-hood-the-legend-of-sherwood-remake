import type { Polygon } from "polygon-clipping";
import type { Point } from "./level.ts";

/** Remove duplicate closure, straight-edge vertices and zero-width backtracking spikes. */
export function simplifyMotionRing(points: Point[]): Point[] {
  const result = points.map((p): Point => [...p]);
  if (
    result.length > 1 &&
    result[0]![0] === result.at(-1)![0] &&
    result[0]![1] === result.at(-1)![1]
  )
    result.pop();
  let changed = true;
  while (changed && result.length >= 3) {
    changed = false;
    for (let i = 0; i < result.length; i++) {
      const a = result[(i + result.length - 1) % result.length]!,
        b = result[i]!,
        c = result[(i + 1) % result.length]!;
      if (Math.abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) < 1e-8) {
        result.splice(i, 1);
        changed = true;
        break;
      }
    }
  }
  return result;
}

function collinear(points: Point[]): boolean {
  const a = points[0];
  if (!a) return true;
  const b = points.find((p) => p[0] !== a[0] || p[1] !== a[1]);
  return !b || points.every((p) => (b[0] - a[0]) * (p[1] - a[1]) === (b[1] - a[1]) * (p[0] - a[0]));
}

/** Only boolean-operation output may lose zero-area rings on the integer grid. */
export function quantizeGeneratedMotionPolygon(
  polygon: Polygon,
  quantize: (value: number) => number,
  label: string,
  warnings: string[],
): Polygon | null {
  if (!polygon.length) throw new Error(`${label}: missing polygon boundary`);
  const result: Polygon = [];
  for (const [index, original] of polygon.entries()) {
    // Clipping may insert a fractional vertex on a straight edge. Rounding
    // that redundant vertex first creates a kink and can open a false seam.
    const points = simplifyMotionRing(original).map(([x, y]): Point => [quantize(x), quantize(y)]);
    if (
      points.length &&
      original.length > 1 &&
      original[0]![0] === original.at(-1)![0] &&
      original[0]![1] === original.at(-1)![1]
    )
      points.push([...points[0]!]);
    if (collinear(simplifyMotionRing(points))) {
      warnings.push(
        `${label}: generated ${index === 0 ? "region" : "hole"} collapsed to zero area on the integer movement grid and was omitted.`,
      );
      if (index === 0) return null;
    } else result.push(points);
  }
  return result;
}
