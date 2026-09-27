import test from "node:test";
import assert from "node:assert/strict";
import {
  recoveryClipping as clipping,
  recoveryPolygonBoolean,
} from "./recovery-polygon-boolean.ts";
import { polygonArea } from "./recover-ground-gameplay.ts";
import type { Polygon } from "polygon-clipping";

const box = (x: number, y: number, size: number): Polygon => [
  [
    [x, y],
    [x + size, y],
    [x + size, y + size],
    [x, y + size],
  ],
];
test("fixed-point recovery preserves holes, islands and coincident boundaries", () => {
  const shell = box(0, 0, 100),
    hole = box(20, 20, 60),
    island = box(40, 40, 20);
  const donut = clipping.difference(shell, hole);
  const result = clipping.union(donut, island);
  assert.equal(polygonArea(result), 6800);
  assert.equal(result.length, 2);
  assert.equal(result.filter((p) => p.length === 2).length, 1);
  assert.equal(polygonArea(clipping.intersection(result, hole)), 400);
  assert.equal(polygonArea(clipping.xor(result, clipping.union(island, donut))), 0);
  assert.equal(polygonArea(clipping.union(shell, box(100, 0, 100))), 20000);
  assert.equal(polygonArea(clipping.intersection(shell, hole, island)), 400);
  assert.equal(polygonArea(clipping.xor(shell, hole, hole)), 10000);
});
test("movement-grid normalization repairs touching rings and supports signed map coordinates", () => {
  const result = recoveryPolygonBoolean(
    "union",
    [box(-100, -100, 100)[0]!, box(-90, -90, 89.6)[0]!],
    [],
    1,
  );
  assert.equal(polygonArea(result), 1900);
  assert.deepEqual(clipping.intersection([], box(0, 0, 10)), []);
  assert.throws(() => clipping.union(box(Infinity, 0, 1)), /coordinate range/);
  assert.throws(() => clipping.union(box(1e10, 0, 1)), /coordinate range/);
});
