import test from "node:test";
import assert from "node:assert/strict";
import {
  createTerrainGrid,
  subdivideTerrainCells,
  terrainHeightAt,
  terrainTriangles,
  validateTerrainGrid,
  terrainGameplay,
  type TerrainGrid,
} from "./authored-terrain.ts";
import { deleteTerrainVertices } from "./terrain-delete.ts";
import type { Level3D } from "./level3d.ts";

const vertex = (grid: TerrainGrid, x: number, y: number) =>
  grid.vertices.find((v) => v.position[0] === x && v.position[1] === y)!.id;
const area = (grid: TerrainGrid) =>
  terrainTriangles({ terrain: grid }).reduce(
    (sum, { points: [a, b, c] }) =>
      sum + ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2,
    0,
  );
function conforming(grid: TerrainGrid) {
  validateTerrainGrid(grid);
  const used = new Set(grid.cells.flatMap((c) => c.vertices));
  assert.equal(used.size, grid.vertices.length);
  for (const cell of grid.cells)
    for (let i = 0; i < cell.vertices.length; i++) {
      const a = grid.vertices[cell.vertices[i]!]!.position,
        b = grid.vertices[cell.vertices[(i + 1) % cell.vertices.length]!]!.position;
      for (const p of grid.vertices.map((v) => v.position)) {
        const cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
        assert.ok(
          Math.abs(cross) > 1e-7 ||
            (p[0] - a[0]) * (p[0] - b[0]) + (p[1] - a[1]) * (p[1] - b[1]) >= -1e-8,
          "no hanging retained vertex on a triangle edge",
        );
      }
    }
}
test("dissolving an interior grid vertex reconnects ground without changing distant cells", () => {
  const grid = createTerrainGrid([0, 0, 400, 400], 100);
  grid.vertices.forEach((v) => {
    v.position[2] = v.position[0] / 10;
    v.uv = [v.position[0] / 400, v.position[1] / 400];
    v.materialMix = { grass_short: 0.25, path_dirt: 0.75 };
  });
  const before = structuredClone(grid),
    id = vertex(grid, 100, 100);
  const result = deleteTerrainVertices(grid, [id]);
  conforming(result);
  assert.equal(area(result), area(grid));
  assert.equal(terrainHeightAt({ terrain: result }, 100, 100), 10);
  for (let x = 5; x < 400; x += 17)
    for (let y = 7; y < 400; y += 19)
      assert.ok(Math.abs(terrainHeightAt({ terrain: result }, x, y)! - x / 10) < 1e-7);
  for (const v of result.vertices)
    assert.strictEqual(
      v,
      grid.vertices.find((old) => old.id === v.id),
    );
  const distant = grid.cells.at(-1)!;
  const retained = result.cells.find((c) => c.id === distant.id)!;
  assert.deepEqual(
    retained.vertices.map((i) => result.vertices[i]!.id),
    distant.vertices.map((i) => grid.vertices[i]!.id),
  );
  assert.deepEqual(grid, before);
  const gameplay = terrainGameplay({
    version: 1,
    map: "dissolve",
    size: null,
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    objects: [],
    groups: [],
    sceneAssets: [],
    terrain: result,
  } as Level3D)!;
  assert.ok(gameplay.gameplay!.surfaces.length > 0);
});
test("boundary dissolution trims a corner and preserves collinear boundary samples", () => {
  const grid = createTerrainGrid([0, 0, 300, 300], 100);
  const corner = deleteTerrainVertices(grid, [vertex(grid, 0, 0)]);
  conforming(corner);
  assert.equal(area(corner), 85000);
  assert.equal(terrainHeightAt({ terrain: corner }, 10, 10), undefined);
  const edge = deleteTerrainVertices(grid, [vertex(grid, 100, 0)]);
  conforming(edge);
  assert.equal(area(edge), 90000);
});
test("adjacent and disconnected selections dissolve only their incident patches", () => {
  for (const positions of [
    [
      [100, 100],
      [200, 100],
    ],
    [
      [100, 100],
      [400, 400],
    ],
    [
      [100, 100],
      [300, 300],
    ],
  ]) {
    const grid = createTerrainGrid([0, 0, 500, 500], 100),
      result = deleteTerrainVertices(
        grid,
        positions.map(([x, y]) => vertex(grid, x!, y!)),
      );
    conforming(result);
    assert.equal(area(result), 250000);
  }
});
test("retained interior vertices stay connected even inside a multiply selected patch", () => {
  const grid = createTerrainGrid([0, 0, 400, 400], 100);
  const selected = [
    [100, 100],
    [200, 100],
    [300, 100],
    [100, 200],
    [300, 200],
    [100, 300],
    [200, 300],
    [300, 300],
  ].map(([x, y]) => vertex(grid, x!, y!));
  const center = grid.vertices.find((v) => v.id === vertex(grid, 200, 200))!;
  center.position[2] = 50;
  const result = deleteTerrainVertices(grid, selected);
  conforming(result);
  assert.equal(area(result), 160000);
  assert.strictEqual(
    result.vertices.find((v) => v.id === center.id),
    center,
  );
  assert.equal(terrainHeightAt({ terrain: result }, 200, 200), 50);
});
test("patch cycles preserve an untouched island and existing holes", () => {
  for (const hole of [false, true]) {
    const grid = createTerrainGrid([0, 0, 500, 500], 100);
    const center = grid.cells[12]!;
    if (hole) grid.cells = grid.cells.filter((c) => c !== center);
    const selected = [];
    for (let x = 1; x <= 4; x++)
      for (let y = 1; y <= 4; y++)
        if (x === 1 || x === 4 || y === 1 || y === 4) selected.push(vertex(grid, x * 100, y * 100));
    const result = deleteTerrainVertices(grid, selected);
    conforming(result);
    assert.equal(area(result), hole ? 240000 : 250000);
    assert.equal(terrainHeightAt({ terrain: result }, 250, 250), hole ? undefined : 0);
    if (!hole) assert.ok(result.cells.some((c) => c.id === center.id));
  }
});
test("subdivided irregular terrain retains source appearance and vertex data", () => {
  let grid = createTerrainGrid([0, 0, 300, 300], 100, 0, "ground_rocky");
  grid = subdivideTerrainCells(grid, [grid.cells[0]!.id]);
  const chosen = grid.vertices.find((v) => v.position[0] === 50 && v.position[1] === 50)!;
  chosen.position[0] = 45;
  chosen.position[1] = 55;
  const result = deleteTerrainVertices(grid, [chosen.id]);
  conforming(result);
  assert.equal(area(result), 90000);
  assert.ok(result.cells.every((c) => c.material === "ground_rocky"));
});
test("invalid deletion is atomic and empty selection is an identity no-op", () => {
  const grid = createTerrainGrid([0, 0, 100, 100], 100),
    before = structuredClone(grid);
  assert.strictEqual(deleteTerrainVertices(grid, []), grid);
  assert.throws(() => deleteTerrainVertices(grid, ["missing"]), /unknown vertex/);
  assert.throws(
    () =>
      deleteTerrainVertices(
        grid,
        grid.vertices.map((v) => v.id),
      ),
    /three vertices/,
  );
  assert.throws(
    () => deleteTerrainVertices(grid, [grid.vertices[0]!.id, grid.vertices[1]!.id]),
    /three vertices/,
  );
  assert.deepEqual(grid, before);
});

test("concave boundary shortcuts cannot swallow an untouched island", () => {
  const positions: [number, number, number][] = [
    [0, 0, 0],
    [100, 0, 0],
    [100, 100, 0],
    [60, 100, 0],
    [60, 40, 0],
    [0, 40, 0],
    [35, 50, 0],
    [45, 50, 0],
    [40, 55, 0],
  ];
  const grid: TerrainGrid = {
    version: 1,
    spacing: 100,
    vertices: positions.map((position, i) => ({ id: `v${i}`, position })),
    cells: [
      { id: "concave", vertices: [0, 1, 2, 3, 4, 5], material: "grass_short" },
      { id: "island", vertices: [6, 7, 8], material: "path_dirt" },
    ],
  };
  validateTerrainGrid(grid);
  const before = structuredClone(grid);
  assert.throws(() => deleteTerrainVertices(grid, ["v4"]), /overlap another cell/);
  assert.deepEqual(grid, before);
});

test("reconnected cells retain fallback appearance and walkability of the local patch", () => {
  const grid = createTerrainGrid([0, 0, 300, 300], 100);
  const id = vertex(grid, 100, 100);
  const selectedIndex = grid.vertices.findIndex((v) => v.id === id);
  const local = grid.cells.filter((c) => c.vertices.includes(selectedIndex));
  for (const cell of local) {
    cell.material = "ground_rocky";
    cell.walkable = false;
  }
  const result = deleteTerrainVertices(grid, [id]);
  for (const cell of result.cells.filter((c) => c.id.includes("/dissolved"))) {
    assert.equal(cell.material, "ground_rocky");
    assert.equal(cell.walkable, false);
  }
  for (const original of grid.cells.filter((c) => !local.includes(c))) {
    const unchanged = result.cells.find((c) => c.id === original.id)!;
    assert.equal(unchanged.material, original.material);
    assert.equal(unchanged.walkable, original.walkable);
  }
});
