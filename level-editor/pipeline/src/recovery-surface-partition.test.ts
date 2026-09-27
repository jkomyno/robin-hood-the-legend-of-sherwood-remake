import test from "node:test";
import assert from "node:assert/strict";
import clipping, { type Polygon } from "polygon-clipping";
import { partitionRecoverySurfaces } from "./recovery-surface-partition.ts";
import { polygonArea } from "./recover-ground-gameplay.ts";

const rect = (x: number, y: number, w: number, h: number): Polygon => [
  [
    [x, y],
    [x + w, y],
    [x + w, y + h],
    [x, y + h],
    [x, y],
  ],
];

test("overlapping projections choose highest bounding height and preserve ground and holes", () => {
  const boundary = rect(0, 0, 100, 100),
    hole = rect(0, 0, 10, 10);
  const result = partitionRecoverySurfaces(
    boundary,
    [hole],
    [
      { polygon: rect(20, 20, 40, 40), maximumHeight: 10 },
      { polygon: rect(40, 40, 40, 40), maximumHeight: 20 },
    ],
  );
  assert.equal(polygonArea(result.surfaces[0]!), 1200);
  assert.equal(polygonArea(result.surfaces[1]!), 1600);
  assert.equal(polygonArea(result.ground), 7100);
  assert.equal(polygonArea(clipping.intersection(result.surfaces[0]!, result.surfaces[1]!)), 0);
  const assembled = clipping.union(result.ground, ...result.surfaces);
  assert.equal(polygonArea(clipping.xor(assembled, clipping.difference(boundary, hole))), 0);
});

test("equal-height projections keep source order, including a fully covered surface", () => {
  const polygon = rect(0, 0, 100, 100);
  const result = partitionRecoverySurfaces(
    polygon,
    [],
    [
      { polygon, maximumHeight: 10 },
      { polygon, maximumHeight: 10 },
    ],
  );
  assert.equal(polygonArea(result.surfaces[0]!), 10000);
  assert.deepEqual(result.surfaces[1], []);
  assert.deepEqual(result.ground, []);
});
