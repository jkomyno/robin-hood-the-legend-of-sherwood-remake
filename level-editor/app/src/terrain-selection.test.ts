import test from "node:test";
import assert from "node:assert/strict";
import { createTerrainGrid } from "@rle/shared";
import { flattenTerrainVertices } from "./terrain-selection.ts";

test("flatten averages only selected heights and preserves their XY and all unselected data", () => {
  const grid = createTerrainGrid([0, 0, 200, 100], 100, 90);
  grid.vertices[0]!.position[2] = -20;
  grid.vertices[1]!.position[2] = 10;
  grid.vertices[3]!.position[2] = 70;
  const ids = [0, 1, 3].map((index) => grid.vertices[index]!.id);
  const flattened = flattenTerrainVertices(grid, [...ids, ids[0]!]);
  assert.strictEqual(flattened.cells, grid.cells);
  for (let i = 0; i < grid.vertices.length; i++) {
    const before = grid.vertices[i]!,
      after = flattened.vertices[i]!;
    if (ids.includes(before.id)) {
      assert.deepEqual(after.position, [before.position[0], before.position[1], 20]);
      assert.equal(after.material, before.material);
    } else assert.strictEqual(after, before);
  }
  assert.deepEqual(
    [grid.vertices[0]!.position[2], grid.vertices[1]!.position[2], grid.vertices[3]!.position[2]],
    [-20, 10, 70],
  );
});

test("flatten empty and single selections is unchanged and invalid selections fail explicitly", () => {
  const grid = createTerrainGrid([0, 0, 100, 100], 100);
  assert.strictEqual(flattenTerrainVertices(grid, []), grid);
  assert.strictEqual(flattenTerrainVertices(grid, [grid.vertices[0]!.id]), grid);
  assert.throws(() => flattenTerrainVertices(grid, ["missing"]), /unknown terrain vertex/);
});
