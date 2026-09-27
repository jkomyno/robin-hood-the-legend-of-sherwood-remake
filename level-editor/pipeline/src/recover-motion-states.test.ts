import test from "node:test";
import assert from "node:assert/strict";
import type { MotionArea, Patch, Point } from "../../shared/src/level.ts";
import { recoverMotionStates } from "./recover-motion-states.ts";
import { recoverGroundGameplay } from "./recover-ground-gameplay.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { diagnoseGameplayCandidates } from "./diagnose-gameplay-candidates.ts";

const box = (x: number, width: number): Point[] => [
  [x, 0],
  [x + width, 0],
  [x + width, 100],
  [x, 100],
];
test("changing obstacles do not erase their stable ground or become permanent terrain holes", () => {
  const area: MotionArea = {
    is_lift: false,
    state_id: 0,
    polygon: { points: box(0, 100) },
    skeleton_segments: [],
    flags: 0,
    obstacles: [0, 1, 2, 0x80000000].map((state_id, i) => ({
      state_id,
      polygon: { points: box(i * 20, 10) },
    })),
  };
  const patches = [0, 15].map((pair) => ({
    pathfinder_sector: 7,
    pathfinder_layer: 0,
    pathfinder_changing_obstacles: pair,
  })) as unknown as Patch[];
  const { base, transitions } = recoverMotionStates(area, 7, 0, patches);
  assert.equal(base.obstacles.length, 1);
  assert.equal(area.obstacles.length, 4);
  assert.deepEqual(
    transitions.map((t) => [t.pair, t.patches, t.initial.length, t.applied.length]),
    [
      [0, [0], 1, 1],
      [15, [1], 0, 1],
    ],
  );
  const ground = recoverGroundGameplay([base], []);
  assert.equal(ground.sourceArea, 9000);
  assert.equal(ground.differenceArea, 0);
  assert.equal(recoverMotionStates(area, 99, 0, patches).transitions[0]!.patches.length, 0);
  area.obstacles[1]!.state_id = 3;
  assert.throws(() => recoverMotionStates(area, 7, 0, patches), /Combined movement/);
});
test("a successful stable geometry probe cannot certify missing movement transitions", () => {
  const { document, assets } = assetCompilerFixture();
  const report = diagnoseGameplayCandidates(document, assets, { omittedMovementTransitions: 2 });
  assert.equal(report.staticGeometry.ready, true);
  assert.equal(report.staticGeometry.omittedMovementTransitions, 2);
  assert.equal(report.compilation.ready, false);
  assert.match(report.compilation.error!, /movement transition definitions \(2\)/);
});
