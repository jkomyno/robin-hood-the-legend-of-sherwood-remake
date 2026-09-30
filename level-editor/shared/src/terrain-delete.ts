import earcut from "earcut";
import { fixedPolygonBoolean } from "./fixed-polygon-boolean.ts";
import { validateTerrainGrid, type TerrainGrid, type TerrainCell } from "./authored-terrain.ts";
import type { Point } from "./level.ts";

const edgeKey = (a: number, b: number) => (a < b ? `${a}/${b}` : `${b}/${a}`);
const signedArea = (points: Point[]) =>
  points.reduce((sum, a, i) => {
    const b = points[(i + 1) % points.length]!;
    return sum + a[0] * b[1] - b[0] * a[1];
  }, 0) / 2;
const cross = (a: Point, b: Point, c: Point) =>
  (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
const fail = (reason: string): never => {
  throw new Error(`Cannot delete terrain vertices: ${reason}`);
};

/** Dissolve selected vertices within their incident cells, retaining all other vertex data. */
export function deleteTerrainVertices(grid: TerrainGrid, ids: Iterable<string>): TerrainGrid {
  const wanted = new Set(ids);
  if (!wanted.size) return grid;
  const known = new Map(grid.vertices.map((vertex, index) => [vertex.id, index]));
  for (const id of wanted) if (!known.has(id)) fail(`unknown vertex ${id}`);
  const removed = new Set([...wanted].map((id) => known.get(id)!));
  if (grid.vertices.length - removed.size < 3) fail("at least three vertices must remain");
  const point = (index: number): Point => grid.vertices[index]!.position.slice(0, 2) as Point;
  const affected = grid.cells.filter((cell) => cell.vertices.some((index) => removed.has(index)));
  const untouched = grid.cells.filter((cell) => !cell.vertices.some((index) => removed.has(index)));
  const edges = new Map<string, { a: number; b: number; cells: TerrainCell[] }>();
  for (const cell of affected)
    for (let i = 0; i < cell.vertices.length; i++) {
      const a = cell.vertices[i]!,
        b = cell.vertices[(i + 1) % cell.vertices.length]!,
        key = edgeKey(a, b);
      const edge = edges.get(key);
      if (edge) {
        if (edge.cells.length > 1 || edge.a === a)
          fail("incident cells have overlapping or non-manifold edges");
        edge.cells.push(cell);
      } else edges.set(key, { a, b, cells: [cell] });
    }
  const neighbors = new Map(affected.map((cell) => [cell, [] as TerrainCell[]]));
  for (const edge of edges.values())
    if (edge.cells.length === 2) {
      neighbors.get(edge.cells[0]!)!.push(edge.cells[1]!);
      neighbors.get(edge.cells[1]!)!.push(edge.cells[0]!);
    }
  const components: TerrainCell[][] = [],
    visited = new Set<TerrainCell>();
  for (const cell of affected) {
    if (visited.has(cell)) continue;
    const component = [cell];
    visited.add(cell);
    for (let i = 0; i < component.length; i++)
      for (const next of neighbors.get(component[i]!)!)
        if (!visited.has(next)) {
          visited.add(next);
          component.push(next);
        }
    components.push(component);
  }
  const generated: TerrainCell[] = [],
    occupied = new Set(grid.cells.map((cell) => cell.id));
  for (const component of components) {
    const members = new Set(component),
      boundary = [...edges.values()].filter(
        (edge) => edge.cells.length === 1 && members.has(edge.cells[0]!),
      );
    const outgoing = new Map<number, number>();
    for (const edge of boundary) {
      if (outgoing.has(edge.a))
        fail("the selected patch has a pinched boundary; delete smaller selections");
      outgoing.set(edge.a, edge.b);
    }
    const rings: number[][] = [];
    while (outgoing.size) {
      const start = outgoing.keys().next().value!,
        cycle: number[] = [];
      let current = start;
      do {
        cycle.push(current);
        const next = outgoing.get(current);
        if (next === undefined) fail("the selected patch has an open boundary");
        outgoing.delete(current);
        current = next!;
      } while (current !== start);
      const ring = cycle.filter((index) => !removed.has(index));
      if (ring.length < 3) fail("a boundary or existing hole would collapse");
      const oldArea = signedArea(cycle.map(point)),
        newArea = signedArea(ring.map(point));
      if (Math.abs(newArea) < 1e-5 || oldArea * newArea <= 0)
        fail("a boundary would invert or collapse");
      rings.push(ring);
    }
    const outers = rings.filter((ring) => signedArea(ring.map(point)) > 0);
    if (outers.length !== 1) fail("the selected patch cannot form one simple surrounding boundary");
    const outer = outers[0]!,
      holes = rings.filter((ring) => ring !== outer),
      ordered = [outer, ...holes];
    const boundaryEdges = ordered.flatMap((ring) =>
      ring.map((a, i) => [a, ring[(i + 1) % ring.length]!] as const),
    );
    for (let i = 0; i < boundaryEdges.length; i++)
      for (const [c, d] of boundaryEdges.slice(i + 1)) {
        const [a, b] = boundaryEdges[i]!;
        if (a === c || a === d || b === c || b === d) continue;
        if (
          cross(point(a), point(b), point(c)) * cross(point(a), point(b), point(d)) < -1e-8 &&
          cross(point(c), point(d), point(a)) * cross(point(c), point(d), point(b)) < -1e-8
        )
          fail("reconnected boundary edges would cross");
      }
    const indices = ordered.flat(),
      offsets: number[] = [];
    let offset = outer.length;
    for (const hole of holes) {
      offsets.push(offset);
      offset += hole.length;
    }
    const flat = indices.flatMap(point),
      triangulated = earcut(flat, offsets);
    let triangles: number[][] = [];
    for (let i = 0; i < triangulated.length; i += 3) {
      const triangle = triangulated.slice(i, i + 3).map((index) => indices[index]!);
      if (cross(...(triangle.map(point) as [Point, Point, Point])) < 0) triangle.reverse();
      triangles.push(triangle);
    }
    const retained = [...new Set(component.flatMap((cell) => cell.vertices))].filter(
      (index) => !removed.has(index),
    );
    // Earcut may omit collinear boundary points. Also insert every surviving
    // interior point so dissolution never orphans an unselected height sample.
    for (const index of retained) {
      const p = point(index);
      let used = triangles.some((triangle) => triangle.includes(index));
      triangles = triangles.flatMap((triangle) => {
        if (triangle.includes(index)) return [triangle];
        for (let e = 0; e < 3; e++) {
          const a = triangle[e]!,
            b = triangle[(e + 1) % 3]!,
            c = triangle[(e + 2) % 3]!;
          const pa = point(a),
            pb = point(b);
          if (
            Math.abs(cross(pa, pb, p)) < 1e-7 &&
            (p[0] - pa[0]) * (p[0] - pb[0]) + (p[1] - pa[1]) * (p[1] - pb[1]) < -1e-8
          ) {
            used = true;
            return [
              [a, index, c],
              [index, b, c],
            ];
          }
        }
        return [triangle];
      });
      if (used) continue;
      const containing = triangles.findIndex((triangle) =>
        triangle.every((a, i) => cross(point(a), point(triangle[(i + 1) % 3]!), p) > 1e-7),
      );
      if (containing < 0) fail("the new boundary would strand a remaining vertex");
      const [a, b, c] = triangles[containing]!;
      triangles.splice(containing, 1, [a!, b!, index], [b!, c!, index], [c!, a!, index]);
    }
    const expectedArea = ordered.reduce((sum, ring) => sum + signedArea(ring.map(point)), 0);
    const actualArea = triangles.reduce(
      (sum, triangle) => sum + signedArea(triangle.map(point)),
      0,
    );
    if (
      !triangles.length ||
      Math.abs(expectedArea - actualArea) > Math.max(1e-6, expectedArea * 1e-8)
    )
      fail("the patch cannot be triangulated without changing its boundary or holes");
    const sources = component.map((cell) => ({ cell, polygon: [cell.vertices.map(point)] }));
    for (const triangle of triangles) {
      const polygon = [triangle.map(point)];
      let source = component[0]!,
        largest = -1;
      for (const candidate of sources) {
        const area = fixedPolygonBoolean("intersection", polygon, [candidate.polygon]).reduce(
          (sum, poly) =>
            sum +
            poly.reduce((part, ring, i) => part + (i ? -1 : 1) * Math.abs(signedArea(ring)), 0),
          0,
        );
        if (area > largest) {
          source = candidate.cell;
          largest = area;
        }
      }
      // Explicit vertex material data stays unchanged. Only fallback cell
      // appearance and walkability follow the old cell covering most of a triangle.
      let id = `${source.id}/dissolved`,
        serial = 1;
      while (occupied.has(id)) id = `${source.id}/dissolved-${serial++}`;
      occupied.add(id);
      generated.push({ ...source, id, vertices: triangle, diagonal: undefined });
    }
  }
  const geometry = (cell: TerrainCell) => {
    const polygon = [cell.vertices.map(point)];
    const xs = polygon[0]!.map((p) => p[0]),
      ys = polygon[0]!.map((p) => p[1]);
    return {
      polygon,
      bounds: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)],
    };
  };
  const coverage = untouched.map(geometry);
  for (const cell of generated) {
    const next = geometry(cell),
      b = next.bounds;
    for (const other of coverage) {
      const a = other.bounds;
      if (a[2]! <= b[0]! || b[2]! <= a[0]! || a[3]! <= b[1]! || b[3]! <= a[1]!) continue;
      const overlap = fixedPolygonBoolean("intersection", next.polygon, [other.polygon]);
      if (overlap.some((polygon) => Math.abs(signedArea(polygon[0]!)) > 1e-6))
        fail("reconnected ground would overlap another cell");
    }
    coverage.push(next);
  }
  const remap = new Map<number, number>(),
    vertices = grid.vertices.filter((_, index) => {
      if (removed.has(index)) return false;
      remap.set(index, remap.size);
      return true;
    });
  const cells = [...untouched, ...generated].map((cell) => {
    const mapped = cell.vertices.map((index) => remap.get(index)!);
    return mapped.every((index, i) => index === cell.vertices[i])
      ? cell
      : { ...cell, vertices: mapped };
  });
  if (!cells.length) fail("no ground would remain");
  const result = { ...grid, vertices, cells };
  validateTerrainGrid(result);
  return result;
}
