import test from "node:test";
import assert from "node:assert/strict";
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
