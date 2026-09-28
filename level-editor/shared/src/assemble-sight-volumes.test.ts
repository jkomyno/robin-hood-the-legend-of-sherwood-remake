import assert from "node:assert/strict";
import test from "node:test";
import { assembleSightVolumes, type PlacedSightJoin } from "./assemble-sight-volumes.ts";
import type { CompiledAssetGeometry } from "./asset-gameplay.ts";
import { assetCompilerFixture } from "../test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "./compile-asset-gameplay.ts";

function fixture() {
  const geometry: CompiledAssetGeometry = {
    motion_data: { layers: [], graph_bytes: [] },
    doors: [],
    sight_obstacles: [0, 10, 50].map((x) => ({
      points: [
        [x, 0],
        [x + 10, 0],
        [x + 10, 10],
        [x, 10],
      ].map(([x, y]) => ({ x: x!, y: y!, z_bottom: 0, z_top: 5 })),
      opaque: true,
      solid: true,
      mouse: true,
      show_shadow_polygon: true,
      default_material: 0,
      projection_area: null,
      material_indices: [],
    })),
  };
  const joins: PlacedSightJoin[] = [
    {
      index: 0,
      edge: [
        [10, 0, 0],
        [10, 10, 0],
      ],
    },
    {
      index: 1,
      edge: [
        [10, 10, 0],
        [10, 0, 0],
      ],
    },
  ];
  return { geometry, joins };
}
test("matching seams remove internal faces and rebuild unrelated sight references", () => {
  const { geometry, joins } = fixture();
  geometry.masks = [
    {
      layer: 0,
      mask_type: 1,
      character_polyline: [],
      projectile_polyline: null,
      box_top_left: [0, 0],
      box_size: [0, 0],
      mask_data: [],
      obstacle_indices: [2],
    },
  ];
  geometry.movement_transitions = [
    {
      id: "unrelated",
      waypoint: [0, 0],
      sector: 0,
      layer: 0,
      active: true,
      definitive: false,
      apply_polygon: { points: [] },
      no_apply_polygon: { points: [] },
      motion_changes: [],
      initial_sight: [2],
      applied_sight: [],
    },
  ];
  assembleSightVolumes(geometry, joins);
  assert.equal(geometry.sight_obstacles.length, 2);
  assert.equal(geometry.sight_obstacles[0]!.points.length, 4);
  assert.deepEqual(new Set(geometry.sight_obstacles[0]!.points.map((p) => p.x)), new Set([0, 20]));
  assert.deepEqual(geometry.masks[0]!.obstacle_indices, [1]);
  assert.deepEqual(geometry.movement_transitions[0]!.initial_sight, [1]);
});
test("unmatched seams remain independent and ambiguous or incompatible joins fail", () => {
  const missing = fixture();
  assembleSightVolumes(missing.geometry, missing.joins.slice(0, 1));
  assert.equal(missing.geometry.sight_obstacles.length, 3);
  const flags = fixture();
  flags.geometry.sight_obstacles[1]!.opaque = false;
  assert.throws(() => assembleSightVolumes(flags.geometry, flags.joins), /flags or heights/);
  const ambiguous = fixture();
  ambiguous.joins.push(structuredClone(ambiguous.joins[1]!));
  assert.throws(() => assembleSightVolumes(ambiguous.geometry, ambiguous.joins), /Ambiguous/);
  const height = fixture();
  height.geometry.sight_obstacles[0]!.points[0]!.z_top = 6;
  assert.throws(() => assembleSightVolumes(height.geometry, height.joins), /flat/);
  const outside = fixture();
  outside.joins[0]!.edge[0][0] = 9;
  assert.throws(() => assembleSightVolumes(outside.geometry, outside.joins), /complete directed/);
  const receiving = fixture();
  receiving.geometry.sight_obstacles[0]!.projection_area = [0, 0];
  assert.throws(() => assembleSightVolumes(receiving.geometry, receiving.joins), /unlinked/);
  const material = fixture();
  material.geometry.sight_obstacles[0]!.material_indices = [0];
  assert.throws(() => assembleSightVolumes(material.geometry, material.joins), /unlinked/);
});

test("rotated seam assemblies retain their outer contour", () => {
  const { geometry, joins } = fixture();
  for (const shape of geometry.sight_obstacles)
    for (const p of shape.points) [p.x, p.y] = [100 - p.y, 200 + p.x];
  for (const join of joins)
    for (const point of join.edge) [point[0], point[1]] = [100 - point[1], 200 + point[0]];
  assembleSightVolumes(geometry, joins);
  assert.equal(geometry.sight_obstacles.length, 2);
  assert.deepEqual(
    new Set(geometry.sight_obstacles[0]!.points.map((p) => `${p.x},${p.y}`)),
    new Set(["100,200", "100,220", "90,220", "90,200"]),
  );
});
test("compiler assembles opted-in asset copies and separates them after movement", () => {
  const { document, assets, hut } = assetCompilerFixture();
  const part = hut.parts[0]!;
  part.obstacle_local_game!.points = [
    [40, 40],
    [50, 40],
    [50, 50],
    [40, 50],
  ].map(([x, y]) => ({ x: x!, y: y!, z_bottom: 0, z_top: 30 }));
  part.sight_join_edges = [
    [
      [50, 40, 0],
      [50, 50, 0],
    ],
    [
      [40, 50, 0],
      [40, 40, 0],
    ],
  ];
  hut.gameplay!.doors = [];
  hut.gameplay!.movementBlockers = [];
  document.objects[0]!.obstacle = structuredClone(part.obstacle_local_game!);
  const object = structuredClone(document.objects[0]!);
  object.id += "-copy";
  object.group = "copy";
  const group = structuredClone(document.groups[0]!);
  group.id = "copy";
  group.transform.dx += 10;
  document.objects.push(object);
  document.groups.push(group);
  const before = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  assert.equal(before.sight_obstacles.length, 1);
  assert.equal(before.sight_obstacles[0]!.points.length, 4);
  group.transform.dx += 10;
  const moved = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  assert.equal(moved.sight_obstacles.length, 2);
});
