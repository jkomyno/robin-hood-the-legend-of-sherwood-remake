import assert from "node:assert/strict";
import test from "node:test";
import { orderSightVolumes } from "./order-sight-volumes.ts";
import { compileAssetGameplay } from "./compile-asset-gameplay.ts";
import { maskAssetCompilerFixture, assetCompilerFixture } from "../test-fixtures/asset-gameplay.ts";

test("query ordering remaps masks and changing sight while preserving equal-order stability", () => {
  const { document, assets } = maskAssetCompilerFixture();
  const geometry = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const first = geometry.sight_obstacles[0]!;
  geometry.sight_obstacles.push(structuredClone(first), structuredClone(first));
  geometry.movement_transitions![0]!.initial_sight = [0, 2];
  geometry.movement_transitions![0]!.applied_sight = [1];
  const original = [...geometry.sight_obstacles];
  const mapping = new Map(original.map((_, i) => [i, i]));
  orderSightVolumes(
    geometry,
    new Map([
      [0, 9],
      [1, 2],
      [2, 2],
    ]),
    mapping,
  );
  assert.equal(geometry.sight_obstacles[0], original[1]);
  assert.equal(geometry.sight_obstacles[1], original[2]);
  assert.equal(geometry.sight_obstacles[2], original[0]);
  assert.deepEqual(geometry.masks![0]!.obstacle_indices, [2]);
  assert.deepEqual(geometry.movement_transitions![0]!.initial_sight, [2, 1]);
  assert.deepEqual(geometry.movement_transitions![0]!.applied_sight, [0]);
  assert.throws(
    () =>
      orderSightVolumes(
        geometry,
        new Map([
          [0, 1],
          [1, 2],
        ]),
        new Map([
          [0, 0],
          [1, 0],
        ]),
      ),
    /disagree/,
  );
});

test("compiler uses asset query order for physical parts and explicit volumes", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.doors = [];
  const part = hut.parts[0]!;
  const {
    projection_area: _area,
    material_indices: _materials,
    ...shape
  } = structuredClone(part.obstacle_local_game!);
  for (const p of shape.points) p.x += 100;
  hut.gameplay!.volumes = [{ id: "extra", node: part.node, shape }];
  hut.gameplay!.sightOrder = { [part.node]: 5, extra: 1 };
  const geometry = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  assert(geometry.sight_obstacles[0]!.points[0]!.x > geometry.sight_obstacles[1]!.points[0]!.x);
  hut.gameplay!.sightOrder.extra = -1;
  assert.throws(() => compileAssetGameplay(document, assets, [0, 0, 2000, 2000]), /query order/);
  hut.gameplay!.sightOrder = { missing: 1 };
  assert.throws(() => compileAssetGameplay(document, assets, [0, 0, 2000, 2000]), /query order/);
});
