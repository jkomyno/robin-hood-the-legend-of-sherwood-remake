import test from "node:test";
import assert from "node:assert/strict";
import { preserveMovementBoundary } from "./preserve-movement-boundary.ts";
import type { Point } from "./level.ts";
import { fixedPolygonBoolean } from "./fixed-polygon-boolean.ts";

const boundary: Point[] = [
  [0, 0],
  [100, 0],
  [100, 100],
  [0, 100],
];

test("preserved movement boundaries discard unrelated blockers but retain crossing contours", () => {
  const result = preserveMovementBoundary(
    boundary,
    [
      [
        [
          [50, -10],
          [60, -10],
          [60, 110],
          [50, 110],
        ],
      ],
      [
        [
          [200, 200],
          [210, 200],
          [210, 210],
          [200, 210],
        ],
      ],
    ],
    [],
  );
  assert.equal(result.blockers.length, 1);
  assert.deepEqual(result.blockers[0], [
    [50, -10],
    [60, -10],
    [60, 110],
    [50, 110],
  ]);
  assert.deepEqual(result.polygon, boundary);
});

test("preserved movement boundaries retain enclosed walkable islands", () => {
  const obstacles: Point[][] = [
    [
      [10, 10],
      [90, 10],
      [90, 90],
      [10, 90],
    ],
    [
      [30, 30],
      [70, 30],
      [70, 70],
      [30, 70],
    ],
  ];
  const result = preserveMovementBoundary(boundary, [obstacles], []);
  assert.equal(result.blockers.length, 8);
  assert.deepEqual(
    fixedPolygonBoolean(
      "xor",
      obstacles,
      result.blockers.map((p) => [p]),
    ),
    [],
  );
  assert(result.blockers.flat().every((p) => p.every(Number.isInteger)));
});

test("preserved movement boundaries reject collapsed envelopes", () => {
  assert.throws(
    () =>
      preserveMovementBoundary(
        [
          [0, 0],
          [0.1, 0],
          [0, 0.1],
        ],
        [],
        [],
      ),
    /collapsed/,
  );
});
