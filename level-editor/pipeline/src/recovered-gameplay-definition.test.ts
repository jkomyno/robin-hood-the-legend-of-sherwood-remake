import test from "node:test";
import assert from "node:assert/strict";
import {
  liftAssetCompilerFixture,
  interiorAssetCompilerFixture,
  joinedInteriorCompilerFixture,
  movementTransitionCompilerFixture,
  doorTransitionCompilerFixture,
  doorAnchorCompilerFixture,
  projectionMaterialCompilerFixture,
  maskAssetCompilerFixture,
} from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import {
  recoveredGameplayDefinition,
  descriptorGameplayPacket,
  type RecoveredGameplayPacket,
} from "./recovered-gameplay-definition.ts";
import type { AssetGameplay, AssetDoor } from "../../shared/src/asset-gameplay.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";

test("unrestricted passage continuity survives authoring conversion", () => {
  const { hut } = assetCompilerFixture();
  hut.gameplay!.doors[0]!.polygon = [];
  hut.gameplay!.doors[0]!.allowContinuous = true;
  const recovered = recoveredGameplayDefinition(packetFromFixture(hut.gameplay!), hut);
  assert.equal(recovered.doors[0]!.allowContinuous, true);
});

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
    materials: gameplay.materials,
    surfaces: gameplay.surfaces.map((s) => ({
      id: s.id,
      node: s.node,
      projectionMaterials: s.projectionMaterials,
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
        interiorJoins: room.joins,
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

test("asset mask coverage and state links survive recovery packet conversion independently", () => {
  const { hut } = maskAssetCompilerFixture();
  const packet = packetFromFixture(hut.gameplay!);
  packet.masks = hut.gameplay!.masks;
  packet.movementTransitions = hut.gameplay!.movementTransitions;
  const result = recoveredGameplayDefinition(packet, hut);
  assert.deepEqual(result.masks, packet.masks);
  assert.deepEqual(result.movementTransitions, packet.movementTransitions);
  result.masks![0]!.triangles[0]![0][0] += 10;
  result.movementTransitions![0]!.initialMasks!.push("extra");
  assert.notDeepEqual(result.masks, packet.masks);
  assert.notDeepEqual(result.movementTransitions, packet.movementTransitions);
});

test("receiving material references survive recovery without sharing draft metadata", () => {
  const { hut } = projectionMaterialCompilerFixture();
  const packet = packetFromFixture(hut.gameplay!);
  packet.surfaces[0]!.projectionMaterials!.priorityHeight = 25;
  packet.surfaces[0]!.projectionMaterials!.priority = 3;
  const restored = recoveredGameplayDefinition(packet, hut);
  assert.deepEqual(
    restored.surfaces[0]!.projectionMaterials,
    packet.surfaces[0]!.projectionMaterials,
  );
  assert.deepEqual(restored.materials, packet.materials);
  packet.surfaces[0]!.projectionMaterials!.regions.length = 0;
  assert.deepEqual(restored.surfaces[0]!.projectionMaterials!.regions, ["inlay"]);
});

test("recovered door links retain endpoint identities and independent draft data", () => {
  const { hut, document, assets } = doorTransitionCompilerFixture();
  const expected = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const packet = packetFromFixture(hut.gameplay!);
  const ids = new Map(
    packet.connections.flatMap((connection) =>
      connection.endpoints.map(
        (endpoint) => [endpoint.id, `${connection.id}/${endpoint.id}`] as const,
      ),
    ),
  );
  packet.movementTransitions = structuredClone(hut.gameplay!.movementTransitions);
  for (const transition of packet.movementTransitions!)
    transition.doorLinks!.ids = transition.doorLinks!.ids.map((id) => ids.get(id)!);
  hut.gameplay = recoveredGameplayDefinition(packet, hut);
  packet.movementTransitions![0]!.doorLinks!.ids[0] = "missing";
  assert.deepEqual(
    compileAssetGameplay(document, assets, [0, 0, 2000, 2000]).movement_transitions,
    expected.movement_transitions,
  );
});

test("reviewed movement transitions survive draft conversion without shared mutable data", () => {
  const { hut, document, assets } = movementTransitionCompilerFixture();
  const packet = packetFromFixture(hut.gameplay!);
  packet.movementTransitions = structuredClone(hut.gameplay!.movementTransitions);
  const expected = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  hut.gameplay = recoveredGameplayDefinition(packet, hut);
  assert.deepEqual(hut.gameplay.movementTransitions, packet.movementTransitions);
  packet.movementTransitions![0]!.waypoint[0] += 100;
  assert.notDeepEqual(hut.gameplay.movementTransitions, packet.movementTransitions);
  assert.deepEqual(
    compileAssetGameplay(document, assets, [0, 0, 2000, 2000]).movement_transitions,
    expected.movement_transitions,
  );
});

test("geometry-only assets retain derived movement collision unless explicitly replaced", () => {
  const { document, assets, hut } = assetCompilerFixture();
  const expected = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const seed = descriptorGameplayPacket(hut);
  assert.equal(seed.movementBlockers, undefined);
  const packet = packetFromFixture(hut.gameplay!);
  delete packet.movementBlockers;
  hut.gameplay = recoveredGameplayDefinition(packet, hut);
  assert.deepEqual(compileAssetGameplay(document, assets, [0, 0, 2000, 2000]), expected);
  assert.equal(hut.gameplay.movementBlockers, undefined);
  assert.equal(
    recoveredGameplayDefinition(
      descriptorGameplayPacket(assets.get("marker")!),
      assets.get("marker")!,
    ).collision,
    "none",
  );
});

test("selected permanent solids survive authoring conversion without sharing the draft list", () => {
  const { hut } = assetCompilerFixture();
  const packet = packetFromFixture(hut.gameplay!);
  delete packet.movementBlockers;
  packet.movementSolids = ["building-999"];
  const gameplay = recoveredGameplayDefinition(packet, hut);
  assert.deepEqual(gameplay.movementSolids, ["building-999"]);
  packet.movementSolids.length = 0;
  assert.deepEqual(gameplay.movementSolids, ["building-999"]);
});

test("mission surface recovery uses local geometry without retaining projection references", () => {
  const { hut } = assetCompilerFixture();
  const shape = structuredClone(hut.parts[0]!.obstacle_local_game!);
  shape.projection_area = [123, 45];
  hut.parts = [
    {
      node: "bridge",
      name: "Bridge",
      mission_profile: "unused-authoring-reference",
      obstacle_local_game: shape,
    },
  ];
  const gameplay = recoveredGameplayDefinition(descriptorGameplayPacket(hut), hut);
  assert.deepEqual(gameplay.surfaces[0]!.height, [30, 30, 30, 30]);
  assert.deepEqual(gameplay.surfaces[0]!.polygon, [
    [40, 40],
    [50, 40],
    [50, 50],
    [40, 50],
  ]);
  assert.ok(!JSON.stringify(gameplay).includes("projection_area"));
  hut.editor_usage = "map-background";
  assert.throws(() => descriptorGameplayPacket(hut), /terrain needs authored movement boundaries/);
});

for (const fixture of [
  liftAssetCompilerFixture,
  interiorAssetCompilerFixture,
  doorAnchorCompilerFixture,
])
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

test("interior passage sockets survive authoring conversion without sharing draft data", () => {
  const { document, assets, hut, annex, passage } = joinedInteriorCompilerFixture();
  for (const descriptor of [hut, annex]) descriptor.gameplay!.movementBlockers = [];
  for (const group of document.groups) group.transform.dx += 100;
  const expected = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  for (const descriptor of [hut, annex]) {
    const packet = packetFromFixture(descriptor.gameplay!);
    packet.asset = descriptor.id;
    descriptor.gameplay = recoveredGameplayDefinition(packet, descriptor);
    assert.notEqual(descriptor.gameplay.interiors![0]!.joins, packet.connections[0]!.interiorJoins);
  }
  assert.deepEqual(compileAssetGameplay(document, assets, [0, 0, 2000, 2000]), expected);
  const packet = packetFromFixture(passage.gameplay!);
  packet.asset = passage.id;
  const converted = recoveredGameplayDefinition(packet, passage);
  assert.deepEqual(converted.interiors, passage.gameplay!.interiors);
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
