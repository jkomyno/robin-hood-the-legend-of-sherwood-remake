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
  projectionVolumeCompilerFixture,
  maskAssetCompilerFixture,
  joinedNavigationCompilerFixture,
} from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import {
  recoveredGameplayDefinition,
  descriptorGameplayPacket,
  type RecoveredGameplayPacket,
} from "./recovered-gameplay-definition.ts";
import type { AssetGameplay, AssetDoor } from "../../shared/src/asset-gameplay.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";

test("recovery converts query precedence into independent asset definitions", () => {
  const { hut } = assetCompilerFixture();
  const packet = descriptorGameplayPacket(hut);
  packet.sightOrder = { [hut.parts[0]!.node]: 7 };
  const definition = recoveredGameplayDefinition(packet, hut);
  assert.deepEqual(definition.sightOrder, packet.sightOrder);
  packet.sightOrder[hut.parts[0]!.node] = 99;
  assert.equal(definition.sightOrder![hut.parts[0]!.node], 7);
});

test("recovery retains independently authored movement envelopes", () => {
  const { hut } = assetCompilerFixture();
  const packet = packetFromFixture(hut.gameplay!);
  packet.surfaces[0]!.navigationRegion = "ground";
  packet.surfaces[0]!.preserveMovementPrecision = true;
  packet.surfaces[0]!.preserveMovementBoundary = true;
  const definition = recoveredGameplayDefinition(packet, hut);
  assert.equal(definition.surfaces[0]!.preserveMovementBoundary, true);
  assert.equal(definition.surfaces[0]!.preserveMovementPrecision, true);
  packet.surfaces[0]!.vertices[0]![0] += 1;
  assert.notEqual(definition.surfaces[0]!.polygon[0]![0], packet.surfaces[0]!.vertices[0]![0]);
});

test("unrestricted passage continuity survives authoring conversion", () => {
  const { hut } = assetCompilerFixture();
  hut.gameplay!.doors[0]!.polygon = [];
  hut.gameplay!.doors[0]!.allowContinuous = true;
  const recovered = recoveredGameplayDefinition(packetFromFixture(hut.gameplay!), hut);
  assert.equal(recovered.doors[0]!.allowContinuous, true);
});

test("navigation joins survive packet conversion as independent local geometry", () => {
  const { hut } = joinedNavigationCompilerFixture();
  const packet = packetFromFixture(hut.gameplay!);
  const recovered = recoveredGameplayDefinition(packet, hut);
  assert.deepEqual(
    recovered.surfaces[0]!.navigationJoins,
    hut.gameplay!.surfaces[0]!.navigationJoins,
  );
  packet.surfaces[0]!.navigationJoins![0]![0][0] += 1;
  assert.notDeepEqual(recovered.surfaces[0]!.navigationJoins, packet.surfaces[0]!.navigationJoins);
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
      navigationRegion: s.navigationRegion,
      navigationJoins: s.navigationJoins,
      projectionMaterials: s.projectionMaterials,
      projectionVolume: s.projectionVolume,
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

test("receiving volumes and state bindings survive authoring conversion", () => {
  const { hut } = projectionVolumeCompilerFixture();
  const packet = packetFromFixture(hut.gameplay!);
  packet.volumes = hut.gameplay!.volumes;
  packet.movementSolids = [];
  packet.movementTransitions = hut.gameplay!.movementTransitions;
  const restored = recoveredGameplayDefinition(packet, hut);
  assert.equal(restored.surfaces[0]!.projectionVolume, "platform-volume");
  assert.deepEqual(restored.volumes, packet.volumes);
  assert.deepEqual(restored.movementTransitions, packet.movementTransitions);
  packet.volumes![0]!.shape.points[0]!.z_bottom = 5;
  assert.equal(restored.volumes![0]!.shape.points[0]!.z_bottom, 15);
});

test("asset mask coverage and state links survive recovery packet conversion independently", () => {
  const { hut } = maskAssetCompilerFixture();
  const packet = packetFromFixture(hut.gameplay!);
  packet.masks = hut.gameplay!.masks;
  packet.maskOcclusionNodes = ["building-999"];
  packet.movementTransitions = hut.gameplay!.movementTransitions;
  const result = recoveredGameplayDefinition(packet, hut);
  assert.deepEqual(result.masks, packet.masks);
  assert.deepEqual(result.maskOcclusionNodes, packet.maskOcclusionNodes);
  assert.notEqual(result.maskOcclusionNodes, packet.maskOcclusionNodes);
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
  packet.surfaces[0]!.projectionMaterials!.planePoints = [
    [100, 0, 20],
    [100, 100, 20],
    [0, 0, 20],
  ];
  const restored = recoveredGameplayDefinition(packet, hut);
  assert.deepEqual(
    restored.surfaces[0]!.projectionMaterials,
    packet.surfaces[0]!.projectionMaterials,
  );
  assert.deepEqual(restored.materials, packet.materials);
  packet.surfaces[0]!.projectionMaterials!.regions.length = 0;
  packet.surfaces[0]!.projectionMaterials!.planePoints[0][0] = 999;
  assert.equal(restored.surfaces[0]!.projectionMaterials!.planePoints![0][0], 100);
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

test("empty authored movement ownership disables derived collision without removing sight", () => {
  const { document, assets, hut } = assetCompilerFixture();
  const before = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const packet = packetFromFixture(hut.gameplay!);
  packet.movementBlockers = [];
  hut.gameplay = recoveredGameplayDefinition(packet, hut);
  const after = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  assert.deepEqual(hut.gameplay.movementBlockers, []);
  assert(before.motion_data.layers.flat().some((area) => area.obstacles.length));
  assert(after.motion_data.layers.flat().every((area) => area.obstacles.length === 0));
  assert.deepEqual(after.sight_obstacles, before.sight_obstacles);
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

test("preview bounds cannot create a walkable surface from a projection placeholder", () => {
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
  assert.deepEqual(gameplay.surfaces, []);
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

test("lift surfaces sharing a frame require explicit independent bindings", () => {
  const { hut } = liftAssetCompilerFixture();
  const packet = packetFromFixture(hut.gameplay!);
  const first = packet.surfaces.find((s) => s.kind === "lift")!;
  const second = { ...structuredClone(first), id: "second-ladder-surface" };
  packet.surfaces.push(second);
  const connection = packet.connections.find((c) => c.kind === "lift")!;
  const another = structuredClone(connection);
  another.id = "second-ladder";
  for (const endpoint of another.endpoints) endpoint.id = `second-${endpoint.id}`;
  packet.connections.push(another);
  assert.throws(() => recoveredGameplayDefinition(packet, hut), /found 2/);
  connection.surface = first.id;
  another.surface = second.id;
  const recovered = recoveredGameplayDefinition(packet, hut);
  assert.deepEqual(
    recovered.lifts!.map((lift) => lift.surface),
    [first.id, second.id],
  );
  another.surface = "missing-surface";
  assert.throws(() => recoveredGameplayDefinition(packet, hut), /found 0/);
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
