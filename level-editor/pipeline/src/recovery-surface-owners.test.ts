import test from "node:test";
import assert from "node:assert/strict";
import type { Polygon } from "polygon-clipping";
import clipping from "polygon-clipping";
import { recoverSurfaceOwners } from "./recovery-surface-owners.ts";
import { polygonArea } from "./recover-ground-gameplay.ts";
import { distanceToPolygon } from "./recovery-elevation.ts";

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
test("a shared asset cut retains the outer movement boundary and its landing", () => {
  const footprints = [rectangle(0.4, 9.6), rectangle(10, 19.6)];
  const region = [rectangle(0, 30)];
  const exact = recoverSurfaceOwners(region, footprints);
  const cut = recoverSurfaceOwners(region, footprints, true);
  assert.ok(distanceToPolygon([0, 5], exact.owned[0]![0]![0]!) > 0);
  assert.equal(distanceToPolygon([0, 5], cut.owned[0]![0]![0]!), 0);
  assert.deepEqual(cut.owned.map(polygonArea), [100, 200]);
  assert.equal(cut.unresolvedArea, 0);
  assert.equal(cut.warnings.length, 1);
});
test("missing or overlapping cuts do not invent an ownership partition", () => {
  const result = recoverSurfaceOwners(
    [rectangle(0, 40)],
    [rectangle(0.1, 19.8), rectangle(10.1, 19.8)],
    true,
  );
  assert.ok(result.unresolvedArea > 200);
  assert.equal(result.warnings.length, 0);
  const gap = recoverSurfaceOwners([rectangle(0, 40)], [rectangle(0, 10), rectangle(11, 29)], true);
  assert.equal(gap.unresolvedArea, 10);
});
test("shared cuts retain holes and remain valid after a rigid placement transform", () => {
  const rotate = (polygon: Polygon): Polygon =>
    polygon.map((ring) => ring.map(([x, y]) => [100 - y, 200 + x]));
  const region: Polygon = [
    ...rectangle(0, 30),
    [
      [4, 2],
      [6, 2],
      [6, 4],
      [4, 4],
      [4, 2],
    ],
  ];
  const result = recoverSurfaceOwners(
    [rotate(region)],
    [rectangle(0.4, 9.6), rectangle(10, 19.6)].map(rotate),
    true,
  );
  assert.deepEqual(result.owned.map(polygonArea), [96, 200]);
  assert.equal(result.unresolvedArea, 0);
  assert.equal(polygonArea(clipping.xor(result.owned.flat(), [rotate(region)])), 0);
});
