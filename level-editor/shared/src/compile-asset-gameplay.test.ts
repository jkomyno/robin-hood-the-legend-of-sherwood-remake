import test from "node:test";
import assert from "node:assert/strict";
import { compileAssetGameplay } from "./compile-asset-gameplay.ts";
import { validateAssetGameplay } from "./asset-gameplay.ts";
import { IDENTITY_TRANSFORM } from "./level3d.ts";
import {
  assetCompilerFixture,
  slopedAssetCompilerFixture,
} from "../test-fixtures/asset-gameplay.ts";

import { heightPlane, planeHeight } from "./gameplay-plane.ts";

const bounds: [number, number, number, number] = [0, 0, 2000, 2000];
test("asset-only compilation constructs motion areas, fresh references and doors", () => {
  const { document, assets } = assetCompilerFixture();
  const result = compileAssetGameplay(document, assets, bounds);
  assert.equal(result.motion_data.layers.length, 2);
  assert.equal(result.motion_data.layers[0]!.length, 2);
  assert.deepEqual(result.motion_data.graph_bytes, []);
  assert.deepEqual(result.spawn, {
    position: [320, 320],
    sector: 0,
    layer: 0,
    projection_area: null,
  });
  assert.deepEqual(result.sight_obstacles[0]!.material_indices, []);
  assert.equal(result.doors[0]!.sector_out, 0);
  assert.equal(result.doors[0]!.sector_in, 2);
  assert.deepEqual(result.doors[0]!.point_out, [380, 350]);
  delete document.sourceMap;
  document.objects[0]!.source = { map: "other", obstacle: 0 };
  document.objects[0]!.obstacle = undefined;
  assert.deepEqual(compileAssetGameplay(document, assets, bounds), result);
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
  assert.deepEqual(moved.spawn.position, [520, 420]);
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
  assert.deepEqual(result.spawn.position, [320, 220]);
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
  assert.deepEqual(result.spawn.position, [320, 310]);
  const projection = result.sight_obstacles[result.spawn.projection_area!]!;
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
  // A hole is an actual movement exclusion, not just a rendering cutout.
  assets.get("spawn")!.gameplay!.spawns[0]!.position = [75, 70, 37.5];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /found 0/);
});

test("sloped asset placement transforms both the height plane and the spawn", () => {
  const { document, assets } = slopedAssetCompilerFixture();
  document.objects[1]!.group = "hut-a";
  document.groups[0]!.transform = { ...IDENTITY_TRANSFORM, dx: 800, dy: 200, rot_deg: 90, dz: 30 };
  const result = compileAssetGameplay(document, assets, bounds);
  const surface = result.sight_obstacles[result.spawn.projection_area!]!;
  const plane = heightPlane(surface.points.map((p) => [p.x, p.y - p.z_top, p.z_top]));
  // Integer motion positions incur up to half a pixel of projected rounding.
  const quantizationError = 0.5 * (Math.abs(plane[0]) + Math.abs(plane[1]));
  assert.ok(Math.abs(planeHeight(plane, result.spawn.position) - 40) <= quantizationError + 1e-4);
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
