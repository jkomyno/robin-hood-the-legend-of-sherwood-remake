import type { SightObstacle } from "./level.ts";

/** Oriented world-height coefficients with the runtime's binary32 operation order. */
export function nativeProjectionPlane(
  points: NonNullable<SightObstacle["projection_plane"]>,
): [number, number, number] | undefined {
  const f = Math.fround;
  const p = points.map((point) => point.map(f));
  const a = p[1]!.map((v, i) => f(v - p[0]![i]!));
  const b = p[2]!.map((v, i) => f(v - p[0]![i]!));
  let nx = f(f(a[1]! * b[2]!) - f(b[1]! * a[2]!));
  let ny = f(f(a[2]! * b[0]!) - f(b[2]! * a[0]!));
  let nz = f(f(a[0]! * b[1]!) - f(b[0]! * a[1]!));
  // Degenerate anchors must not establish equivalence between different definitions.
  if (!Number.isFinite(nz) || Math.abs(nz) < 1e-9) return undefined;
  const norm = f(Math.sqrt(f(f(f(nx * nx) + f(ny * ny)) + f(nz * nz))));
  if (f(nz / norm) < 0) return nativeProjectionPlane([points[0], points[2], points[1]]);
  nx = f(nx / norm);
  ny = f(ny / norm);
  nz = f(nz / norm);
  const d = f(f(f(-p[0]![0]! * nx) - f(p[0]![1]! * ny)) - f(p[0]![2]! * nz));
  const k = f(-1 / nz);
  const coefficients: [number, number, number] = [f(nx * k), f(ny * k), f(d * k)];
  return coefficients.every(Number.isFinite) ? coefficients : undefined;
}

export function equivalentProjectionPlanes(
  a: SightObstacle["projection_plane"],
  b: SightObstacle["projection_plane"],
): boolean {
  if (!a || !b) return a === b;
  if (a.every((point, i) => point.every((value, j) => Object.is(value, b[i]![j])))) return true;
  const x = nativeProjectionPlane(a),
    y = nativeProjectionPlane(b);
  return !!x && !!y && x.every((v, i) => Object.is(v, y[i]));
}
