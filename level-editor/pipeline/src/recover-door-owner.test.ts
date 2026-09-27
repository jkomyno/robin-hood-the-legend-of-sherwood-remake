import test from "node:test";
import assert from "node:assert/strict";
import { doorOwnershipFootprint, recoverDoorStateOwner } from "./recover-door-owner.ts";
import type { SightObstacle, Point } from "@rle/shared";

test("door ownership excludes supporting terrain and preserves disconnected sloped slices", () => {
  const outline: Point[] = [
    [0, 0],
    [6, 0],
    [6, 6],
    [4, 6],
    [4, 2],
    [2, 2],
    [2, 6],
    [0, 6],
  ];
  const obstacle: SightObstacle = {
    points: outline.map(([x, y]) => ({ x, y, z_bottom: 0, z_top: y })),
    projection_area: null,
    solid: true,
    opaque: true,
    mouse: true,
    show_shadow_polygon: false,
    default_material: 0,
    material_indices: [],
  };
  const slices = doorOwnershipFootprint(obstacle, 3);
  assert.equal(slices.length, 2);
  assert.ok(slices.every((ring) => ring.every((point) => point[1] > 3)));
  assert.deepEqual(doorOwnershipFootprint(obstacle, 6), []);
  obstacle.points.forEach((point) => {
    point.z_top = 3;
  });
  assert.deepEqual(doorOwnershipFootprint(obstacle, 3), []);
  obstacle.points.forEach((point) => {
    point.z_bottom = 30;
    point.z_top = 40;
  });
  assert.deepEqual(doorOwnershipFootprint(obstacle, 3), []);
});

test("door ownership follows all linked state geometry, independent of source indices", () => {
  const owner = { asset: "gate", node: "closed" };
  const owners = new Map([
    [80, [owner]],
    [12, [{ asset: "gate", node: "open" }]],
  ]);
  const patch = { door_indices: [7, 8], old_sight_obstacles: [80], new_sight_obstacles: [12] };
  assert.equal(recoverDoorStateOwner([8], [patch], owners), owner);
  assert.equal(recoverDoorStateOwner([3], [patch], owners), undefined);
  assert.equal(
    recoverDoorStateOwner([8], [{ ...patch, new_sight_obstacles: [13] }], owners),
    undefined,
  );
  owners.set(12, [{ asset: "other", node: "open" }]);
  assert.equal(recoverDoorStateOwner([8], [patch], owners), undefined);
  owners.set(12, [owner, owner]);
  assert.equal(recoverDoorStateOwner([8], [patch], owners), undefined);
});

test("conflicting linked patches and geometry-free permission changes do not invent owners", () => {
  const owners = new Map([
    [1, [{ asset: "first" }]],
    [2, [{ asset: "second" }]],
  ]);
  const patch = { door_indices: [0], old_sight_obstacles: [1], new_sight_obstacles: [] };
  assert.equal(
    recoverDoorStateOwner([0], [patch, { ...patch, old_sight_obstacles: [2] }], owners),
    undefined,
  );
  assert.equal(
    recoverDoorStateOwner([0], [{ ...patch, old_sight_obstacles: [] }], owners),
    undefined,
  );
});
