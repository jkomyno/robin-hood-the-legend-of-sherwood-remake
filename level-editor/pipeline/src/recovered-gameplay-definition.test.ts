import test from "node:test";
import assert from "node:assert/strict";
import {
  liftAssetCompilerFixture,
  interiorAssetCompilerFixture,
} from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import {
  recoveredGameplayDefinition,
  type RecoveredGameplayPacket,
} from "./recovered-gameplay-definition.ts";
import type { AssetGameplay, AssetDoor } from "../../shared/src/asset-gameplay.ts";

function packetFromFixture(gameplay: AssetGameplay): RecoveredGameplayPacket {
  const door = (d: AssetDoor) => ({
    ...d,
    active: d.active ?? true,
    afterTransition: d.afterTransition
      ? {
          player: d.afterTransition.locked,
          unlockable: d.afterTransition.unlockable,
          villains: d.afterTransition.lockedVillains,
          civilians: d.afterTransition.lockedCivilians,
        }
      : undefined,
  });
  return {
    asset: "hut",
    movementBlockers: [],
    surfaces: gameplay.surfaces.map((s) => ({
      id: s.id,
      node: s.node,
      kind: gameplay.lifts?.some((l) => l.surface === s.id) ? "lift" : "walkable",
      vertices: s.polygon.map(([x, y], i) => [
        x,
        y,
        typeof s.height === "number" ? s.height : s.height[i]!,
      ]),
      holes: [],
    })),
    connections: [
      ...(gameplay.lifts ?? []).map((l) => ({
        id: l.id,
        node: l.node,
        kind: "lift" as const,
        type: l.type,
        direction: l.direction,
        endpoints: l.doors.map(door),
      })),
      ...(gameplay.interiors ?? []).map((room) => ({
        id: room.id,
        node: room.node,
        kind: "building-interior" as const,
        endpoints: room.doors.map((d) => ({
          ...door(d),
          polygon: d.polygon.map(([x, y]): [number, number, number] => [x, y, d.outside[2]]),
        })),
      })),
      ...gameplay.doors.map((d) => ({
        id: `passage-${d.id}`,
        node: d.node,
        kind: "passage" as const,
        endpoints: [door(d)],
      })),
    ],
  };
}

for (const fixture of [liftAssetCompilerFixture, interiorAssetCompilerFixture])
  test(`recovered ${fixture.name} produces equivalent compiled connections after placement`, () => {
    const { document, assets, hut } = fixture();
    hut.gameplay!.movementBlockers = [];
    document.groups[0]!.transform.dx += 100;
    document.objects[1]!.transform.dx += 100;
    const expected = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
    const packet = packetFromFixture(hut.gameplay!);
    hut.gameplay = recoveredGameplayDefinition(packet, hut);
    assert.deepEqual(compileAssetGameplay(document, assets, [0, 0, 2000, 2000]), expected);
    assert.ok(!JSON.stringify(hut.gameplay).includes("sourceMap"));
  });

test("draft conversion preserves alternate locks and rejects lost traversal or off-plane holes", () => {
  const { hut } = liftAssetCompilerFixture();
  const packet = packetFromFixture(hut.gameplay!);
  const missing = structuredClone(packet);
  missing.connections = [];
  assert.throws(() => recoveredGameplayDefinition(missing, hut), /no connection definition/);
  const changing = structuredClone(packet);
  const door = changing.connections[0]!.endpoints[0]!;
  door.locks = { player: false, unlockable: false, villains: false, civilians: false };
  door.afterTransition = { ...door.locks, player: true };
  const restored = recoveredGameplayDefinition(changing, hut).lifts![0]!.doors[0]!;
  assert.equal(restored.locked, false);
  assert.equal(restored.afterTransition!.locked, true);
  const pairedLow = structuredClone(packet);
  for (const d of pairedLow.connections[0]!.endpoints) d.type = 5;
  assert.deepEqual(
    recoveredGameplayDefinition(pairedLow, hut).lifts![0]!.doors.map((d) => d.type),
    [5, 5],
  );
  const invalid = structuredClone(packet);
  invalid.surfaces[0]!.holes = [
    [
      [10, 10, 20],
      [20, 10, 20],
      [20, 20, 20],
    ],
  ];
  assert.throws(() => recoveredGameplayDefinition(invalid, hut), /hole is not on/);
  const split = structuredClone(packet);
  split.surfaces.push({ ...structuredClone(split.surfaces.at(-1)!), id: "split" });
  assert.throws(() => recoveredGameplayDefinition(split, hut), /found 2/);
});
