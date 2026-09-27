import test from "node:test";
import assert from "node:assert/strict";
import { recoverDoorStateOwner } from "./recover-door-owner.ts";

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
