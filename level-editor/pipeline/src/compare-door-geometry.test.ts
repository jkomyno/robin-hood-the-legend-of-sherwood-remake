import test from "node:test";
import assert from "node:assert/strict";
import { doorTransitionCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { compareDoorGeometry, type SourceDoorGeometry } from "./compare-door-geometry.ts";

function fixture() {
  const { document, assets } = doorTransitionCompilerFixture();
  const compiled = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const buildings = [{ StandaloneDoors: { doors: compiled.doors } }, ...compiled.buildings!];
  const nativeDoors = [
    ...compiled.buildings!.flatMap((room) => room.Building.doors),
    ...compiled.doors,
  ];
  const sourceDoors = [
    ...compiled.doors,
    ...compiled.buildings!.flatMap((room) => room.Building.doors),
  ];
  const source: SourceDoorGeometry = structuredClone({
    buildings,
    patches: compiled.movement_transitions!.map((transition) => ({
      active: transition.active,
      definitive: transition.definitive,
      waypoint: transition.waypoint,
      apply_sector: transition.apply_polygon,
      no_apply_sector: transition.no_apply_polygon,
      door_triggered: transition.door_links!.mode === "trigger-transition",
      triggers_door: transition.door_links!.mode === "swap-rights",
      door_indices: transition.door_links!.indices.map((i) => sourceDoors.indexOf(nativeDoors[i]!)),
    })),
  });
  return { source, compiled };
}

test("door comparison follows rebuilt allocation and equivalent click polygon winding", () => {
  const { source, compiled } = fixture();
  for (const room of compiled.buildings!)
    for (const door of room.Building.doors) {
      door.sector_in += 100;
      door.door_sector.points.reverse();
      door.door_sector.points.push(door.door_sector.points.shift()!);
    }
  assert.equal(compareDoorGeometry(source, compiled).equivalent, true);
});

test("door comparison detects missing doors, changed rules and linked trigger direction", () => {
  for (const alter of [
    (d: ReturnType<typeof fixture>["compiled"]) => {
      d.doors[0]!.point_mid[0] += 1;
    },
    (d: ReturnType<typeof fixture>["compiled"]) => {
      d.doors[0]!.locked_pc_after_patch = !d.doors[0]!.locked_pc_after_patch;
    },
    (d: ReturnType<typeof fixture>["compiled"]) => {
      d.doors.push(structuredClone(d.doors[0]!));
    },
    (d: ReturnType<typeof fixture>["compiled"]) => {
      d.movement_transitions![0]!.door_links!.mode = "swap-rights";
    },
    (d: ReturnType<typeof fixture>["compiled"]) => {
      d.movement_transitions![0]!.door_links!.indices = [0];
    },
  ]) {
    const { source, compiled } = fixture();
    alter(compiled);
    assert.equal(compareDoorGeometry(source, compiled).equivalent, false);
  }
});

test("door comparison detects room regrouping even when every door remains identical", () => {
  const { source, compiled } = fixture();
  const doors = compiled.buildings![0]!.Building.doors;
  compiled.buildings = doors.map((door) => ({ Building: { doors: [door] } }));
  const result = compareDoorGeometry(source, compiled);
  assert.equal(result.doors.missing, 0);
  assert.equal(result.doors.extra, 0);
  assert.equal(result.rooms.missing, 1);
  assert.equal(result.rooms.extra, 2);
  assert.equal(result.equivalent, false);
});

test("door comparison rejects dangling bindings and reports incomplete recovery", () => {
  const { source, compiled } = fixture();
  compiled.movement_transitions![0]!.door_links!.indices = [100];
  assert.throws(() => compareDoorGeometry(source, compiled), /Invalid door binding/);
  compiled.movement_transitions = [];
  const result = compareDoorGeometry(source, compiled);
  assert.equal(result.bindings.missing, 2);
  assert.equal(result.equivalent, false);
});
