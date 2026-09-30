import test from "node:test";
import assert from "node:assert/strict";
import { recoverMovementClearance } from "./recover-movement-clearance.ts";
import { polygonArea } from "./recover-ground-gameplay.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import clipping, { type MultiPolygon } from "polygon-clipping";

test("clearance recovery intersects the solid footprint with authoritative free movement", () => {
  const solid = assetCompilerFixture().hut.parts[0]!.obstacle_local_game!;
  const free: MultiPolygon = [
    [
      [
        [0, 0],
        [45, 0],
        [45, 100],
        [0, 100],
        [0, 0],
      ],
    ],
  ];
  assert.equal(polygonArea(recoverMovementClearance(free, [0, 0, 0], solid)), 50);
  const padded = recoverMovementClearance(free, [0, 0, 0], solid, 1);
  const footprint: MultiPolygon = [[solid.points.map((p) => [p.x, p.y])]];
  assert.equal(polygonArea(clipping.intersection(padded, footprint)), 50);
  assert.equal(polygonArea(clipping.difference(padded, free)), 0);
  assert.equal(polygonArea(recoverMovementClearance(free, [0, 0, 30], solid)), 0);
  assert.equal(polygonArea(recoverMovementClearance(free, [0, 0, -10], solid)), 0);
});
test("clearances use the projected position on a sloped surface", () => {
  const solid = assetCompilerFixture().hut.parts[0]!.obstacle_local_game!;
  const free: MultiPolygon = [
    [
      [
        [0, 0],
        [100, 0],
        [100, 100],
        [0, 100],
        [0, 0],
      ],
    ],
  ];
  assert.equal(polygonArea(recoverMovementClearance(free, [0, 1, 0], solid)), 50);
});

test("clearance recovery removes floating contact slivers while retaining subpixel openings", () => {
  const solid = assetCompilerFixture().hut.parts[0]!.obstacle_local_game!;
  solid.points = [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100],
  ].map(([x, y]) => ({
    x: x!,
    y: y!,
    z_bottom: 0,
    z_top: 10,
  }));
  const free: MultiPolygon = [
    [
      [
        [20, 20],
        [20 + 1e-12, 20],
        [20, 20 + 1e-12],
        [20, 20],
      ],
    ],
    [
      [
        [30, 30],
        [30.01, 30],
        [30, 30.01],
        [30, 30],
      ],
    ],
  ];
  for (const margin of [0, 1]) {
    const result = recoverMovementClearance(free, [0, 0, 0], solid, margin);
    assert.equal(result.length, 1);
    assert.deepEqual(result[0], free[1]);
  }
});
