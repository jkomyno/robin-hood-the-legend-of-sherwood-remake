import test from "node:test";
import assert from "node:assert/strict";
import type { Polygon } from "polygon-clipping";
import clipping from "polygon-clipping";
import { recoverSurfaceOwners } from "./recovery-surface-owners.ts";
import { polygonArea } from "./recover-ground-gameplay.ts";

const rectangle = (x: number, width: number): Polygon => [
  [
    [x, 0],
    [x + width, 0],
    [x + width, 10],
    [x, 10],
    [x, 0],
  ],
];
test("split asset footprints recover their own surfaces without duplicating a shared source", () => {
  const result = recoverSurfaceOwners([rectangle(0, 30)], [rectangle(0, 10), rectangle(10, 20)]);
  assert.deepEqual(result.owned.map(polygonArea), [100, 200]);
  assert.equal(result.unresolvedArea, 0);
  const moved = result.owned[1]!.map((p) =>
    p.map((r) => r.map(([x, y]): [number, number] => [x + 50, y])),
  );
  const assembled = clipping.union(result.owned[0]!, moved);
  assert.equal(polygonArea(clipping.intersection(assembled, rectangle(10, 20))), 0);
  assert.equal(polygonArea(clipping.intersection(assembled, rectangle(0, 10))), 100);
  assert.equal(polygonArea(clipping.intersection(assembled, rectangle(60, 20))), 200);
});
test("overlaps and gaps remain unresolved instead of assigning another asset's surface", () => {
  const result = recoverSurfaceOwners([rectangle(0, 40)], [rectangle(0, 20), rectangle(10, 20)]);
  assert.deepEqual(result.owned.map(polygonArea), [100, 100]);
  assert.equal(result.unresolvedArea, 200);
  assert.equal(recoverSurfaceOwners([rectangle(0, 40)], []).unresolvedArea, 400);
});
