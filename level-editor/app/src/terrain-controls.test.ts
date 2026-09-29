import test from "node:test";
import assert from "node:assert/strict";
import { resizeTerrainCorner, terrainCorners } from "./terrain-controls.ts";

test("resizing every terrain corner preserves the opposite corner, including crossing", () => {
  const bounds: [number, number, number, number] = [100, 200, 300, 400];
  for (let corner = 0; corner < 4; corner++) {
    const anchor = terrainCorners(bounds)[(corner + 2) % 4]!;
    for (const point of [
      [50, 150],
      [500, 750],
    ] as [number, number][]) {
      const next = resizeTerrainCorner(bounds, corner, point);
      assert.ok(terrainCorners(next).some((p) => p[0] === anchor[0] && p[1] === anchor[1]));
      assert.ok(terrainCorners(next).some((p) => p[0] === point[0] && p[1] === point[1]));
      assert.ok(next[2] >= 1 && next[3] >= 1);
    }
  }
});
test("terrain corners cannot collapse a region to zero width or height", () => {
  const bounds: [number, number, number, number] = [0, 0, 100, 100];
  assert.deepEqual(resizeTerrainCorner(bounds, 0, [100, 100]), [99, 99, 1, 1]);
});
