import test from "node:test";
import assert from "node:assert/strict";
import clipping from "polygon-clipping";
import type { NavigationPiece } from "./assemble-navigation-regions.ts";
import {
  compileTransitionObstacles,
  type PlacedTransitionBlocker,
} from "./compile-movement-transitions.ts";

const boundary: [number, number][] = [
  [0, 0],
  [100, 0],
  [100, 100],
  [0, 100],
];
const blocker: PlacedTransitionBlocker = {
  transition: "gate",
  applied: false,
  plane: [0, 0, 0],
  polygon: [
    [10, 10],
    [90, 10],
    [90, 90],
    [10, 90],
  ],
  holes: [
    [
      [30, 30],
      [30, 70],
      [70, 70],
      [70, 30],
    ],
  ],
};
test("labelled transition fragments rejoin before rounding and remain scoped to each state", () => {
  const left: PlacedTransitionBlocker = {
    transition: "gate",
    applied: false,
    plane: [0, 0, 0],
    holes: [],
    movementContour: "edge",
    polygon: [
      [10, 10],
      [40.3, 10],
      [40.3, 38.21],
      [10, 17],
    ],
  };
  const right: PlacedTransitionBlocker = {
    ...left,
    polygon: [
      [40.3, 10],
      [90, 10],
      [90, 73],
      [40.3, 38.21],
    ],
  };
  const result = compileTransitionObstacles(
    boundary,
    [],
    [0, 0, 0],
    [
      left,
      right,
      { ...left, applied: true },
      { ...right, applied: true },
      { ...left, transition: "other" },
      { ...right, transition: "other" },
    ],
    [],
  );
  assert.deepEqual(
    result.obstacles.map((o) => o.state_id),
    [1, 2, 4],
  );
  for (const obstacle of result.obstacles)
    assert.deepEqual(
      clipping.xor(
        [obstacle.polygon.points],
        [
          [
            [10, 10],
            [90, 10],
            [90, 73],
            [10, 17],
          ],
        ],
      ),
      [],
    );
  const separate = compileTransitionObstacles(
    boundary,
    [],
    [0, 0, 0],
    [left, { ...right, movementContour: "separate" }],
    [],
  );
  assert.equal(separate.obstacles.length, 2);
});
test("preserved state contours retain implicit fractional boundary crossings", () => {
  const triangle: [number, number][] = [
    [0, 0],
    [100, 0],
    [0, 71],
  ];
  const gate: PlacedTransitionBlocker = {
    ...blocker,
    holes: [],
    polygon: [
      [40, -10],
      [60, -10],
      [60, 100],
      [40, 100],
    ],
  };
  const kept = compileTransitionObstacles(triangle, [], [0, 0, 0], [gate], [], undefined, true);
  assert.deepEqual(kept.obstacles[0]!.polygon.points, gate.polygon);
  assert.equal(kept.obstacles[0]!.state_id, 1);
  assert.deepEqual(kept.initial, [gate.polygon]);
  const clipped = compileTransitionObstacles(triangle, [], [0, 0, 0], [gate], []);
  assert.notDeepEqual(clipped.obstacles[0]!.polygon.points, gate.polygon);
  const absent = { ...gate, polygon: gate.polygon.map(([x, y]): [number, number] => [x + 200, y]) };
  assert.equal(
    compileTransitionObstacles(triangle, [], [0, 0, 0], [absent], [], undefined, true).pairs.size,
    0,
  );
});
test("one transition shares state bits across receiving planes and clips to each receiver", () => {
  const receivers: NavigationPiece[] = [
    {
      plane: [0, 0, 0],
      layer: 0,
      polygon: [
        [0, 0],
        [50, 0],
        [50, 100],
        [0, 100],
      ],
      blockers: [],
    },
    {
      plane: [1, 0, -50],
      layer: 1,
      polygon: [
        [50, 0],
        [100, 0],
        [100, 100],
        [50, 100],
      ],
      blockers: [],
    },
  ];
  const result = compileTransitionObstacles(
    boundary,
    [],
    [0, 0, 0],
    [
      { ...blocker, holes: [] },
      { ...blocker, holes: [], plane: [1, 0, -50], applied: true },
      { ...blocker, holes: [], plane: [0, 0, 999], transition: "unrelated" },
    ],
    [],
    receivers,
  );
  assert.deepEqual([...result.pairs], [["gate", 0]]);
  assert.deepEqual(
    result.obstacles.map((o) => o.state_id),
    [1, 2],
  );
  assert.ok(result.obstacles[0]!.polygon.points.every(([x]) => x <= 50));
  assert.ok(result.obstacles[1]!.polygon.points.every(([x]) => x >= 50));
  assert.equal(result.initial.length, 1);
});
test("state blocker holes survive as nonoverlapping triangles", () => {
  const result = compileTransitionObstacles(boundary, [], [0, 0, 0], [blocker], []);
  const area = result.obstacles.reduce(
    (sum, o) =>
      sum +
      Math.abs(
        o.polygon.points.reduce((a, p, i) => {
          const q = o.polygon.points[(i + 1) % o.polygon.points.length]!;
          return a + p[0] * q[1] - q[0] * p[1];
        }, 0),
      ) /
        2,
    0,
  );
  assert.equal(area, 4800);
  assert.ok(result.obstacles.every((o) => o.state_id === 1));
});

test("small state blocker holes do not use their array index as a simplification tolerance", () => {
  const result = compileTransitionObstacles(
    boundary,
    [],
    [0, 0, 0],
    [
      {
        ...blocker,
        holes: [
          [
            [30, 30],
            [31, 30],
            [30, 31],
          ],
        ],
      },
    ],
    [],
  );
  const area = result.obstacles.reduce(
    (sum, obstacle) =>
      sum +
      Math.abs(
        obstacle.polygon.points.reduce((a, p, i) => {
          const q = obstacle.polygon.points[(i + 1) % obstacle.polygon.points.length]!;
          return a + p[0] * q[1] - q[0] * p[1];
        }, 0),
      ) /
        2,
    0,
  );
  assert.equal(area, 6399.5);
});
test("crossing permanent obstacles do not create state coverage outside the movement envelope", () => {
  const crossing: [number, number][] = [
    [50, -20],
    [120, -20],
    [120, 80],
    [50, 80],
  ];
  const outside: PlacedTransitionBlocker = {
    ...blocker,
    holes: [],
    polygon: [
      [105, 10],
      [115, 10],
      [115, 20],
      [105, 20],
    ],
  };
  const result = compileTransitionObstacles(boundary, [crossing], [0, 0, 0], [outside], []);
  assert.equal(result.pairs.size, 0);
  assert.deepEqual(result.obstacles, []);
});
test("state bit pairs remain unsigned and unrelated planes receive no binding", () => {
  const blockers = Array.from({ length: 16 }, (_, i) => ({
    ...blocker,
    holes: [],
    transition: `gate-${i}`,
    applied: true,
  }));
  const result = compileTransitionObstacles(boundary, [], [0, 0, 0], blockers, []);
  assert.equal(result.obstacles.at(-1)!.state_id, 2147483648);
  assert.equal(compileTransitionObstacles(boundary, [], [0, 0, 1], blockers, []).pairs.size, 0);
  blockers.push({ ...blocker, holes: [], transition: "overflow", applied: true });
  assert.throws(
    () => compileTransitionObstacles(boundary, [], [0, 0, 0], blockers, []),
    /More than 16/,
  );
});
