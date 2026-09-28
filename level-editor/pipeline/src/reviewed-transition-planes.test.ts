import test from "node:test";
import assert from "node:assert/strict";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { reviewedTransitionPlanes } from "./reviewed-transition-planes.ts";

test("reviewed contour planes require pinned and associated receiving geometry", () => {
  const { hut } = assetCompilerFixture();
  const receiver = structuredClone(hut.parts[0]!.obstacle_local_game!);
  receiver.projection_area = [5, 2];
  const source = {
    patches: [{ pathfinder_sector: 5, pathfinder_layer: 2 }],
    sight_obstacles: [receiver],
  };
  const definitions = { source_sha256: "pin", entries: [{ patch: 0, receiver: 0 }] };
  const before = structuredClone(source);
  assert.deepEqual(reviewedTransitionPlanes(source, "pin", definitions).get(0), [0, 0, 30]);
  assert.deepEqual(source, before);
  assert.throws(() => reviewedTransitionPlanes(source, "changed", definitions), /source changed/);
  for (const entries of [
    [],
    [{ patch: 1, receiver: 0 }],
    [{ patch: 0, receiver: 1 }],
    [{ patch: 0.5, receiver: 0 }],
    [...definitions.entries, ...definitions.entries],
  ])
    assert.throws(
      () => reviewedTransitionPlanes(source, "pin", { ...definitions, entries }),
      /reviewed entries|unique patch/,
    );
  receiver.projection_area = [6, 2];
  assert.throws(() => reviewedTransitionPlanes(source, "pin", definitions), /associated receiver/);
  receiver.projection_area = [5, 2];
  receiver.points[2] = { ...receiver.points[1]! };
  assert.throws(() => reviewedTransitionPlanes(source, "pin", definitions), /no nondegenerate/);
});
