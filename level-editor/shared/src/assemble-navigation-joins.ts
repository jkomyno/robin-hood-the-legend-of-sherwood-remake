import type { Vec3 } from "./scene.ts";

export type NavigationJoin = [Vec3, Vec3];
export interface PlacedNavigationJoin {
  region: string;
  owner: string;
  edge: NavigationJoin;
  heightTolerance?: number;
}
const near = (a: Vec3, b: Vec3) => Math.hypot(...a.map((n, i) => n - b[i]!)) < 1e-4;
const projectedNear = (a: Vec3, b: Vec3) =>
  Math.hypot(a[0] - b[0], a[1] - a[2] - (b[1] - b[2])) < 1e-4;

/** A socket is a real outer boundary segment, oriented with its surface on the left
 * in projected space. Matching opposite edges therefore cannot join overlapping copies. */
export function orientNavigationJoin(polygon: Vec3[], edge: NavigationJoin): NavigationJoin {
  const projected = polygon.map(([x, y, z]) => [x, y - z]);
  const area = projected.reduce((sum, p, i) => {
    const q = projected[(i + 1) % projected.length]!;
    return sum + p[0]! * q[1]! - q[0]! * p[1]!;
  }, 0);
  if (Math.abs(area) < 1e-7 || near(...edge))
    throw new Error("Navigation join requires a nondegenerate surface and edge");
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i]!,
      b = polygon[(i + 1) % polygon.length]!;
    const delta = b.map((n, j) => n - a[j]!);
    const length2 = delta.reduce((sum, n) => sum + n * n, 0);
    if (length2 < 1e-8) continue;
    const parameters = edge.map(
      (p) => p.reduce((sum, n, j) => sum + (n - a[j]!) * delta[j]!, 0) / length2,
    );
    if (
      parameters.some(
        (t, j) =>
          t < -1e-7 || t > 1 + 1e-7 || !near(edge[j]!, a.map((n, k) => n + t * delta[k]!) as Vec3),
      )
    )
      continue;
    return (parameters[1]! - parameters[0]!) * area > 0 ? edge : [edge[1], edge[0]];
  }
  throw new Error("Navigation join must lie on one outer surface edge at its authored height");
}

/** Explicit sockets must coincide in projection and height unless both owners allow
 * a height step. Detached edges retain independent navigation; multiple matches are errors. */
export function assembleNavigationJoins(joins: PlacedNavigationJoin[]) {
  const identities = new Map(joins.map((join) => [join.region, join.region]));
  const root = (id: string): string => {
    const parent = identities.get(id)!;
    if (parent === id) return id;
    const result = root(parent);
    identities.set(id, result);
    return result;
  };
  const unmatched: PlacedNavigationJoin[] = [];
  for (const join of joins) {
    const meets = (other: PlacedNavigationJoin, a: Vec3, b: Vec3) =>
      near(a, b) ||
      (projectedNear(a, b) &&
        Math.abs(a[2] - b[2]) <= Math.min(join.heightTolerance ?? 0, other.heightTolerance ?? 0));
    const matches = joins.filter(
      (other) =>
        other !== join &&
        ((meets(other, join.edge[0], other.edge[1]) && meets(other, join.edge[1], other.edge[0])) ||
          (meets(other, join.edge[0], other.edge[0]) && meets(other, join.edge[1], other.edge[1]))),
    );
    if (
      matches.length > 1 ||
      matches.some(
        (other) => other.owner === join.owner || projectedNear(join.edge[0], other.edge[0]),
      )
    )
      throw new Error(`Navigation region ${join.region}: ambiguous or overlapping join`);
    const match = matches[0];
    if (!match) {
      unmatched.push(join);
      continue;
    }
    const a = root(join.region),
      b = root(match.region);
    if (a !== b) identities.set(b, a);
  }
  for (const id of identities.keys()) identities.set(id, root(id));
  return { identities, unmatched };
}
