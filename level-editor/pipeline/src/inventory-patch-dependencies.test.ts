import test from "node:test";
import assert from "node:assert/strict";
import { inventoryPatchDependencies } from "./inventory-patch-dependencies.ts";
import type { SightObstacle } from "../../shared/src/level.ts";

const obstacle: SightObstacle = {
  points: [],
  projection_area: null,
  opaque: true,
  solid: true,
  mouse: true,
  show_shadow_polygon: false,
  default_material: 0,
  material_indices: [],
};
const patch = () => ({
  old_sight_obstacles: [0],
  new_sight_obstacles: [],
  old_masks: [{ layer: 1, index: 2 }],
  new_masks: [],
  door_indices: [3],
});

test("shared state links retain each patch and role, including projection activation", () => {
  const second = { ...patch(), old_masks: [{ layer: 2, index: 2 }], new_sight_obstacles: [1] };
  const report = inventoryPatchDependencies(
    [
      { id: "first", patch: patch() },
      { id: "second", patch: second },
    ],
    [obstacle, { ...obstacle, projection_area: [4, 1] }],
  );
  assert.deepEqual(report.projectionChanges, [{ patch: "second", role: "applied", obstacle: 1 }]);
  assert.deepEqual(report.shared, [
    {
      kind: "sight",
      reference: 0,
      uses: [
        { patch: "first", role: "initial" },
        { patch: "second", role: "initial" },
      ],
    },
    {
      kind: "door",
      reference: 3,
      uses: [
        { patch: "first", role: "binding" },
        { patch: "second", role: "binding" },
      ],
    },
  ]);
  second.old_masks[0]!.layer = 1;
  assert.equal(
    inventoryPatchDependencies(
      [
        { id: "first", patch: patch() },
        { id: "second", patch: second },
      ],
      [obstacle, { ...obstacle, projection_area: [4, 1] }],
    ).shared.length,
    3,
  );
});

test("dependency audit does not invent shared ownership within one patch or accept stale links", () => {
  assert.equal(
    inventoryPatchDependencies(
      [{ id: "one", patch: { ...patch(), new_sight_obstacles: [0] } }],
      [obstacle],
    ).shared.length,
    0,
  );
  assert.throws(
    () =>
      inventoryPatchDependencies(
        [
          { id: "one", patch: patch() },
          { id: "one", patch: patch() },
        ],
        [obstacle],
      ),
    /unique/,
  );
  assert.throws(
    () => inventoryPatchDependencies([{ id: "one", patch: patch() }], []),
    /missing sight obstacle/,
  );
  assert.throws(
    () =>
      inventoryPatchDependencies(
        [{ id: "one", patch: { ...patch(), door_indices: [-1] } }],
        [obstacle],
      ),
    /Invalid door/,
  );
});
