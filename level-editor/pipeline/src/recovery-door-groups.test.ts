import test from "node:test";
import assert from "node:assert/strict";
import { recoveryDoorGroups } from "./recovery-door-groups.ts";

test("standalone passages recover independently while interior entrances share a room", () => {
  const doors = [{ point: [10, 10] }, { point: [1500, 1700] }];
  assert.deepEqual(recoveryDoorGroups({ StandaloneDoors: { doors } }), [
    { kind: "passage", doors: [doors[0]], sourceDoor: 0 },
    { kind: "passage", doors: [doors[1]], sourceDoor: 1 },
  ]);
  assert.deepEqual(recoveryDoorGroups({ Building: { doors } }), [
    { kind: "building-interior", doors },
  ]);
  assert.deepEqual(recoveryDoorGroups({ StandaloneDoors: { doors: [] } }), []);
  assert.throws(() => recoveryDoorGroups({}), /Unknown building/);
});
