import test from "node:test";
import assert from "node:assert/strict";
import { compileAssetGameplay } from "./compile-asset-gameplay.ts";
import { validateAssetGameplay } from "./asset-gameplay.ts";
import { IDENTITY_TRANSFORM } from "./level3d.ts";
import {
  assetCompilerFixture,
  slopedAssetCompilerFixture,
  liftAssetCompilerFixture,
  interiorAssetCompilerFixture,
} from "../test-fixtures/asset-gameplay.ts";

import { heightPlane, planeHeight } from "./gameplay-plane.ts";

const bounds: [number, number, number, number] = [0, 0, 2000, 2000];
test("map assets reject mission spawns rather than silently dropping them", () => {
  const { document, assets, hut } = assetCompilerFixture();
  Object.assign(hut.gameplay!, {
    spawns: [{ id: "player", node: "building-999", position: [20, 20, 0] }],
  });
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /spawns belong to missions/);
});
test("authored subpixel surfaces remain errors rather than being silently omitted", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.surfaces[0]!.polygon = [
    [0, 0],
    [0.1, 0],
    [0.1, 100],
    [0, 100],
  ];
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /collapses after coordinate quantization/,
  );
});

test("authored movement contours follow an asset independently of sight and terrain", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.doors = [];
  hut.gameplay!.surfaces = [];
  hut.gameplay!.movementBlockers = [
    {
      id: "clearance",
      node: "building-999",
      polygon: [
        [35, 35],
        [55, 35],
        [55, 55],
        [35, 55],
      ],
      height: 0,
    },
  ];
  const marker = assets.get("marker")!.gameplay!;
  marker.surfaces = [
    {
      id: "terrain",
      node: "scenery-marker",
      polygon: [
        [0, 0],
        [300, 0],
        [300, 200],
        [0, 200],
      ],
      height: 0,
    },
  ];
  const before = compileAssetGameplay(document, assets, bounds);
  const sortedPoints = (points: [number, number][]) =>
    [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  assert.deepEqual(sortedPoints(before.motion_data.layers[0]![0]!.obstacles[0]!.polygon.points), [
    [335, 335],
    [335, 355],
    [355, 335],
    [355, 355],
  ]);
  assert.equal(before.sight_obstacles[0]!.points[0]!.x, 340);
  document.objects[0]!.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    moved.motion_data.layers[0]![0]!.polygon,
    before.motion_data.layers[0]![0]!.polygon,
  );
  assert.deepEqual(sortedPoints(moved.motion_data.layers[0]![0]!.obstacles[0]!.polygon.points), [
    [435, 335],
    [435, 355],
    [455, 335],
    [455, 355],
  ]);
  // A plane-specific blocker no longer blocks ground when raised above it.
  document.objects[0]!.transform.dz = 100;
  assert.equal(
    compileAssetGameplay(document, assets, bounds).motion_data.layers[0]![0]!.obstacles.length,
    0,
  );
});

test("asset-only compilation constructs motion areas, fresh references and doors", () => {
  const { document, assets } = assetCompilerFixture();
  const result = compileAssetGameplay(document, assets, bounds);
  assert.equal(result.motion_data.layers.length, 2);
  assert.equal(result.motion_data.layers[0]!.length, 2);
  assert.deepEqual(result.motion_data.graph_bytes, []);
  assert.equal("marker" in result, false);
  assert.deepEqual(result.sight_obstacles[0]!.material_indices, []);
  assert.equal(result.doors[0]!.sector_out, 0);
  assert.equal(result.doors[0]!.sector_in, 2);
  assert.deepEqual(result.doors[0]!.point_out, [380, 350]);
  delete document.sourceMap;
  document.objects[0]!.source = { map: "other", obstacle: 0 };
  document.objects[0]!.obstacle = undefined;
  assert.deepEqual(compileAssetGameplay(document, assets, bounds), result);
});
test("movement blocker holes preserve walkable islands and invalid contours fail", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.doors = [];
  hut.gameplay!.movementBlockers = [
    {
      id: "courtyard-wall",
      node: "building-999",
      polygon: [
        [10, 10],
        [80, 10],
        [80, 80],
        [10, 80],
      ],
      height: 0,
      holes: [
        [
          [15, 15],
          [70, 15],
          [70, 70],
          [15, 70],
        ],
      ],
    },
  ];
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.equal(compiled.motion_data.layers[0]!.length, 3);
  hut.gameplay!.movementBlockers[0]!.height = [0, 0, 1, 0];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /must be planar/);
});
test("moving, rotating and duplicating assets rebuilds their geometry and connections", () => {
  const { document, assets } = assetCompilerFixture();
  const before = compileAssetGameplay(document, assets, bounds);
  for (const part of document.objects) {
    part.transform.dx += 200;
    part.transform.dy += 100;
  }
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    moved.doors[0]!.point_out,
    before.doors[0]!.point_out.map((v, i) => v + (i ? 100 : 200)),
  );
  // Duplicate the complete asset; local IDs and provenance are intentionally identical.
  const clone = structuredClone(document.objects[0]!);
  clone.id = "hut-b-body";
  clone.group = "hut-b";
  clone.transform = { ...IDENTITY_TRANSFORM };
  document.objects.push(clone);
  document.groups.push({
    id: "hut-b",
    transform: { ...IDENTITY_TRANSFORM, dx: 1100, dy: 400, rot_deg: 90 },
  });
  const duplicated = compileAssetGameplay(document, assets, bounds);
  assert.equal(duplicated.doors.length, 2);
  assert.equal(duplicated.sight_obstacles.length, 2);
  const door = duplicated.doors[1]!;
  assert.notEqual(door.sector_in, duplicated.doors[0]!.sector_in);
  assert.equal(door.point_in[0], door.point_out[0]);
  assert.equal(door.point_in[1] - door.point_out[1], 23); // 40 * sin(35°), quantized
});
test("missing metadata and disconnected doors fail; no level-data fallback", () => {
  const { document, assets, hut } = assetCompilerFixture();
  delete hut.gameplay;
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /Missing asset gameplay definitions.*hut/,
  );
  const fresh = assetCompilerFixture();
  fresh.hut.gameplay!.doors[0]!.inside = [500, 500, 0];
  assert.throws(
    () => compileAssetGameplay(fresh.document, fresh.assets, bounds),
    /inside must resolve/,
  );
  fresh.hut.gameplay!.doors[0]!.node = "absent";
  assert.throws(
    () => validateAssetGameplay(fresh.hut.gameplay, fresh.hut),
    /unknown gameplay node/,
  );
});
test("passages without click polygons retain their navigation endpoints", () => {
  const { document, assets, hut } = assetCompilerFixture();
  const before = compileAssetGameplay(document, assets, bounds);
  hut.gameplay!.doors[0]!.polygon = [];
  const result = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    result.doors,
    before.doors.map((d) => ({ ...d, door_sector: { points: [] } })),
  );
  hut.gameplay!.doors[0]!.polygon = [
    [1, 1],
    [2, 2],
  ];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /invalid gameplay polygon/);
});
test("door transition lock rules remain asset-local and survive placement", () => {
  const { document, assets, hut } = assetCompilerFixture();
  const door = hut.gameplay!.doors[0]!;
  door.locked = true;
  door.unlockable = true;
  door.type = 7;
  door.afterTransition = {
    locked: false,
    unlockable: false,
    lockedVillains: true,
    lockedCivilians: true,
  };
  const result = compileAssetGameplay(document, assets, bounds).doors[0]!;
  assert.equal(result.door_type, 7);
  assert.equal(result.locked_pc, true);
  assert.equal(result.locked_pc_after_patch, false);
  assert.equal(result.unlockable_after_patch, false);
  assert.equal(result.locked_npc_villain_after_patch, true);
  assert.equal(result.locked_npc_civilian_after_patch, true);
  for (const part of document.objects) part.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds).doors[0]!;
  assert.deepEqual(moved.point_in, [result.point_in[0] + 100, result.point_in[1]]);
  assert.equal(moved.locked_npc_villain_after_patch, true);
});
test("adjacent same-height asset surfaces are joined without a blocking seam", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.surfaces[1]!.polygon = [
    [90, 0],
    [200, 0],
    [200, 100],
    [90, 100],
  ];
  hut.gameplay!.doors = [];
  const result = compileAssetGameplay(document, assets, bounds);
  assert.equal(result.motion_data.layers[0]!.length, 1);
  assert.equal(result.motion_data.layers[0]![0]!.obstacles.length, 1);
});

test("elevation translates motion in projected coordinates while sight remains in world coordinates", () => {
  const { document, assets } = assetCompilerFixture();
  for (const part of document.objects) part.transform.dz = 100;
  const result = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(result.doors[0]!.point_out, [380, 250]);
  assert.equal(result.sight_obstacles[0]!.points[0]!.y, 340);
  assert.equal(result.sight_obstacles[0]!.points[0]!.z_bottom, 100);
  assert.deepEqual(result.motion_data.layers[0]![0]!.polygon.points[0], [300, 200]);
  const floor = result.sight_obstacles.find(
    (o) => Array.isArray(o.projection_area) && o.projection_area[0] === 0,
  )!;
  assert.equal(floor.points[0]!.z_top, 100);
  assert.equal(floor.points[0]!.y, 300);
});

test("sloped surfaces preserve height, holes and the intersecting slice of solids", () => {
  const { document, assets, hut } = slopedAssetCompilerFixture();
  const result = compileAssetGameplay(document, assets, bounds);
  const area = result.motion_data.layers[0]![0]!;
  assert.equal(area.obstacles.length, 2); // Authored hole and the solid crossing the ramp.
  const projection = result.sight_obstacles.find((o) => Array.isArray(o.projection_area))!;
  assert.deepEqual(
    projection.points.map((p) => p.z_top),
    [0, 100, 100, 0],
  );
  // Raise the solid above the whole ramp; it must stop blocking navigation.
  for (const point of hut.parts[0]!.obstacle_local_game!.points) {
    point.z_bottom = 110;
    point.z_top = 140;
  }
  assert.equal(
    compileAssetGameplay(document, assets, bounds).motion_data.layers[0]![0]!.obstacles.length,
    1,
  );
});

test("sloped asset placement transforms the height plane without mission content", () => {
  const { document, assets } = slopedAssetCompilerFixture();
  document.objects[1]!.group = "hut-a";
  document.groups[0]!.transform = { ...IDENTITY_TRANSFORM, dx: 800, dy: 200, rot_deg: 90, dz: 30 };
  const result = compileAssetGameplay(document, assets, bounds);
  const surface = result.sight_obstacles.find((o) => Array.isArray(o.projection_area))!;
  const plane = heightPlane(surface.points.map((p) => [p.x, p.y - p.z_top, p.z_top]));
  for (const p of surface.points)
    assert.ok(Math.abs(planeHeight(plane, [p.x, p.y - p.z_top]) - p.z_top) < 1e-4);
  assert.ok(Math.max(...surface.points.map((p) => p.z_top)) > 129);
});

test("non-planar and degenerate surfaces fail instead of silently flattening", () => {
  const { document, assets, hut } = slopedAssetCompilerFixture();
  hut.gameplay!.surfaces[0]!.height = [0, 100, 110, 0];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /must be planar/);
  hut.gameplay!.surfaces[0]!.polygon = [
    [0, 0],
    [10, 0],
    [20, 0],
  ];
  hut.gameplay!.surfaces[0]!.height = 0;
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /nondegenerate/);
});

test("lift surfaces use the reserved layer and rebuild endpoint references", () => {
  const { document, assets } = liftAssetCompilerFixture();
  const result = compileAssetGameplay(document, assets, bounds);
  assert.equal(result.motion_data.layers.length, 3);
  assert.equal(result.motion_data.layers.at(-1)![0]!.is_lift, true);
  assert.equal(result.doors.length, 0);
  const lift = result.lifts![0]!;
  assert.equal(lift.lift_type, 1);
  assert.equal(lift.direction, 4);
  assert.equal(lift.motion_area_index, 3); // Ground blocker occupies sector 1.
  assert.deepEqual(
    lift.doors.map((d) => d.layer_out),
    [0, 1],
  );
  assert.ok(lift.doors.every((d) => d.layer_in === 2 && d.sector_in === 3));
  const clone = structuredClone(document.objects[0]!);
  clone.id = "stairs-copy";
  clone.group = "stairs-copy";
  clone.transform = { ...IDENTITY_TRANSFORM };
  document.objects.push(clone);
  document.groups.push({
    id: "stairs-copy",
    transform: { ...IDENTITY_TRANSFORM, dx: 1000, dy: 700, rot_deg: 90 },
  });
  const duplicated = compileAssetGameplay(document, assets, bounds);
  assert.equal(duplicated.lifts!.length, 2);
  assert.notEqual(duplicated.lifts![0]!.motion_area_index, duplicated.lifts![1]!.motion_area_index);
  assert.equal(duplicated.lifts![1]!.direction, 8);
});

test("lift validation rejects missing traversal endpoints and mismatched surface ownership", () => {
  const { hut, document, assets } = liftAssetCompilerFixture();
  hut.gameplay!.lifts![0]!.doors.pop();
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /at least two traversal doors/,
  );
  hut.gameplay!.lifts![0]!.surface = "absent";
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /needs its own surface/);
});

test("interior entrances share a fresh virtual sector independent of motion polygons", () => {
  const { document, assets } = interiorAssetCompilerFixture();
  const result = compileAssetGameplay(document, assets, bounds);
  const doors = result.buildings![0]!.Building.doors;
  assert.equal(result.doors.length, 1);
  assert.equal(doors.length, 2);
  assert.ok(doors.every((d) => d.sector_in === 4 && d.layer_in === 1 && d.sector_out === 0));
  assert.equal(doors[1]!.locked_pc, true);
  assert.ok(doors.every((d) => d.locked_npc_civilian));
  const clone = structuredClone(document.objects[0]!);
  clone.id = "house-copy";
  clone.group = "house-copy";
  clone.transform.dx += 600;
  document.objects.push(clone);
  document.groups.push({ id: "house-copy", transform: { ...IDENTITY_TRANSFORM } });
  const duplicated = compileAssetGameplay(document, assets, bounds);
  assert.equal(duplicated.buildings!.length, 2);
  assert.notEqual(
    duplicated.buildings![0]!.Building.doors[0]!.sector_in,
    duplicated.buildings![1]!.Building.doors[0]!.sector_in,
  );
});
