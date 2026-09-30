import test from "node:test";
import assert from "node:assert/strict";
import { type Level3D, validateMission, parseStoredMap } from "@rle/shared";
import { compileMap } from "./map-compile.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileMission } from "./compile-mission.ts";
import type { CompiledAssetGeometry } from "../../shared/src/asset-gameplay.ts";

const polygon = {
  points: [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100],
  ] as [number, number][],
};
const area = {
  is_lift: false,
  state_id: 0,
  polygon,
  skeleton_segments: [] as never[],
  flags: 0,
  obstacles: [],
};
const geometry: CompiledAssetGeometry = {
  motion_data: { layers: [[area], [area], []], graph_bytes: [] },
  sight_obstacles: [
    {
      projection_area: [1, 1],
      points: polygon.points.map(([x, y]) => ({ x, y: y + 20, z_top: 20, z_bottom: 20 })),
      opaque: false,
      solid: false,
      mouse: true,
      show_shadow_polygon: false,
      default_material: 0,
      material_indices: [],
    },
  ],
  doors: [],
};
function document(): Level3D {
  return {
    mission: {
      version: 1,
      spawnPoints: [
        { id: "start", name: "Start", position: [30, 50, 20], direction: 4, profile: 0 },
      ],
      soldiers: [
        {
          id: "guard",
          name: "Guard",
          position: [30, 50, 0],
          direction: 8,
          profile: "Guard",
          allegiance: 2,
        },
      ],
    },
  } as Level3D;
}

test("explicit mission markers bind to the corresponding elevation and native sector", () => {
  const result = compileMission(document(), [0, 0, 100, 100], geometry);
  assert.deepEqual(result.spawn_points, [
    { position: [30, 30], direction: 4, profile: 0, sector: 1, layer: 1, projection_area: 0 },
  ]);
  assert.deepEqual(result.soldiers, [
    {
      position: [30, 50],
      direction: 8,
      profile: "Guard",
      allegiance: 2,
      sector: 0,
      layer: 0,
      projection_area: 65535,
    },
  ]);
  assert.deepEqual(result.warnings, []);
});

test("invalid placement warns and omits only the affected marker", () => {
  const doc = document();
  doc.mission!.spawnPoints[0]!.position[2] = 10;
  assert.throws(() => compileMission(doc, [0, 0, 100, 100], geometry), /one walkable surface/);
  const result = compileMission(doc, [0, 0, 100, 100], geometry, true);
  assert.equal(result.spawn_points.length, 0);
  assert.equal(result.soldiers.length, 1);
  assert.match(result.warnings[0]!, /start.*omitted/);
});

test("legacy preview population alone never produces mission entities", () => {
  const doc = document();
  delete doc.mission;
  assert.deepEqual(compileMission(doc, [0, 0, 100, 100], geometry), {
    spawn_points: [],
    soldiers: [],
    warnings: [],
  });
});

test("mission validation rejects duplicate IDs and invalid native fields", () => {
  const mission = document().mission!;
  validateMission(mission);
  mission.soldiers[0]!.id = "start";
  assert.throws(() => validateMission(mission), /Mission:/);
  mission.soldiers[0]!.id = "guard";
  mission.spawnPoints[0]!.direction = 16;
  assert.throws(() => validateMission(mission), /Mission:/);
});

test("map export preserves separate mission authoring in reopenable editor data", () => {
  const fixture = assetCompilerFixture();
  fixture.document.mission = document().mission;
  fixture.document.mission!.spawnPoints[0]!.position = [320, 320, 0];
  fixture.document.mission!.soldiers[0]!.position = [450, 320, 0];
  const compiled = compileMap(fixture.document, [200, 200, 500, 500], fixture.assets);
  assert.equal(compiled.descriptor.spawn_player, false);
  assert.deepEqual(compiled.descriptor.spawn_points?.[0]?.position, [120, 120]);
  assert.deepEqual(compiled.descriptor.soldiers?.[0]?.position, [250, 120]);
  assert.deepEqual(
    parseStoredMap(compiled.editorDocument, fixture.assets).mission,
    fixture.document.mission,
  );
});

test("initial transition blockers exclude mission placements", () => {
  const blocked = structuredClone(geometry);
  blocked.motion_data.layers[0]![0] = { ...area, obstacles: [{ state_id: 1, polygon }] };
  blocked.sight_obstacles[0]!.projection_area = [2, 1];
  const result = compileMission(document(), [0, 0, 100, 100], blocked, true);
  assert.equal(result.soldiers.length, 0);
  assert.equal(result.spawn_points[0]!.sector, 2);
  assert.match(result.warnings[0]!, /guard/);
});

test("resizing omits out-of-frame mission markers even in strict export and retains editor data", () => {
  const doc = document();
  const before = structuredClone(doc);
  const result = compileMission(doc, [0, 0, 100, 40], geometry);
  assert.equal(result.spawn_points.length, 1);
  assert.equal(result.soldiers.length, 0);
  assert.match(result.warnings.join("\n"), /guard.*outside.*retained/);
  assert.deepEqual(doc, before);
});
