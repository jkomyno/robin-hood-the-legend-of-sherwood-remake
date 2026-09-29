import { assetCompilerFixture } from "../test-fixtures/asset-gameplay.ts";
import test from "node:test";
import assert from "node:assert/strict";
import { terrainPatches, validateGroundRegions } from "./authored-terrain.ts";
import { compileAssetGameplay } from "./compile-asset-gameplay.ts";
import { parseLevel3D } from "./validation.ts";
import type { Level3D } from "./level3d.ts";

export function terrainFixture(): Level3D {
  return {
    version: 1,
    map: "Village",
    size: null,
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    objects: [],
    groups: [],
    sceneAssets: [],
    terrain: [
      { id: "field", name: "Field", bounds: [100, 100, 600, 500], material: "grass", height: 0 },
      {
        id: "village",
        name: "Village",
        bounds: [200, 200, 200, 200],
        material: "dirt",
        height: 50,
      },
      { id: "river", name: "River", bounds: [500, 100, 100, 500], material: "water", height: -20 },
    ],
  };
}
const area = (ring: number[][]) =>
  Math.abs(
    ring.reduce((a, p, i) => {
      const q = ring[(i + 1) % ring.length]!;
      return a + p[0]! * q[1]! - q[0]! * p[1]!;
    }, 0),
  ) / 2;

test("terrain regions replace ground even when lower and retain all corners", () => {
  const d = terrainFixture(),
    patches = terrainPatches(d);
  assert.equal(
    patches.reduce((a, p) => a + area(p.polygon) - p.holes.reduce((n, h) => n + area(h), 0), 0),
    600 * 500,
  );
  assert.equal(patches.find((p) => p.material === "water")!.height, -20);
  assert.equal(patches.find((p) => p.material === "dirt")!.polygon.length, 4);
  assert.deepEqual(parseLevel3D(JSON.parse(JSON.stringify(d))).terrain, d.terrain);
});
test("terrain generates height layers, receiving materials and nonwalkable water", () => {
  const compiled = compileAssetGameplay(terrainFixture(), new Map(), [0, 0, 900, 800]);
  assert.ok(compiled.motion_data.layers.length >= 3);
  assert.ok(compiled.sight_obstacles.some((o) => o.default_material === 3));
  assert.ok(compiled.material_sectors?.some((o) => o.material === 5));
  assert.ok(compiled.motion_data.layers.flat().length > 0);
});
test("adjacent grass regions compile as one walking area", () => {
  const d = terrainFixture();
  d.terrain = [
    { id: "a", name: "A", bounds: [100, 100, 100, 100], height: 0, material: "grass" },
    { id: "b", name: "B", bounds: [200, 100, 100, 100], height: 0, material: "grass" },
  ];
  const result = compileAssetGameplay(d, new Map(), [0, 0, 500, 500]);
  assert.equal(result.motion_data.layers.flat().length, 1);
});
test("river strip uses the same curved footprint for carving and navigation", () => {
  const d = terrainFixture();
  d.terrain = d.terrain!.slice(0, 1);
  d.splines = [
    {
      id: "water",
      name: "River",
      kind: "river",
      points: [
        [300, 120, -10],
        [330, 300, -10],
        [300, 580, -10],
      ],
      closed: false,
      width: 45,
      repeatLength: 150,
    },
  ];
  const patches = terrainPatches(d);
  assert.ok(patches.some((p) => p.material === "water" && p.polygon.length > 8));
  assert.doesNotThrow(() => compileAssetGameplay(d, new Map(), [0, 0, 900, 800]));
});
test("invalid terrain does not silently compile", () => {
  assert.throws(
    () => validateGroundRegions([{ ...terrainFixture().terrain![0], height: NaN }]),
    /Terrain/,
  );
  const d = terrainFixture();
  d.splines = [
    {
      id: "r",
      name: "River",
      kind: "river",
      points: [
        [100, 100, 0],
        [200, 100, 10],
      ],
      closed: false,
      width: 40,
      repeatLength: 150,
    },
  ];
  assert.throws(() => terrainPatches(d), /uniform elevation/);
});

test("placed asset floors replace coincident terrain without breaking door ownership", () => {
  const { document, assets } = assetCompilerFixture();
  document.terrain = [
    { id: "base", name: "Ground", bounds: [50, 50, 1600, 1500], height: 0, material: "grass" },
  ];
  const compiled = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  assert.ok(compiled.doors.length > 0);
});

test("an exterior navigation socket joins an asset to surrounding terrain", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.doors = [];
  hut.gameplay!.surfaces = [
    {
      id: "floor",
      node: "building-999",
      height: 0,
      polygon: [
        [0, 0],
        [100, 0],
        [100, 100],
        [0, 100],
      ],
      navigationRegion: "floor",
      navigationJoins: [
        [
          [100, 20, 0],
          [100, 80, 0],
        ],
      ],
    },
  ];
  document.terrain = [
    { id: "field", name: "Field", bounds: [50, 50, 700, 700], height: 0, material: "grass" },
  ];
  const compiled = compileAssetGameplay(document, assets, [0, 0, 1000, 1000]);
  assert.equal(compiled.motion_data.layers.flat().length, 1);
  assert.ok(!compiled.warnings?.some((w) => w.includes("no matching boundary")));
});

test("paved terrain survives save/load and exports as walkable stone", () => {
  const d = terrainFixture();
  d.terrain = [
    { id: "plaza", name: "Plaza", bounds: [100, 100, 300, 300], height: 0, material: "paved" },
  ];
  const reopened = parseLevel3D(JSON.parse(JSON.stringify(d)));
  assert.equal(reopened.terrain![0]!.material, "paved");
  const compiled = compileAssetGameplay(reopened, new Map(), [0, 0, 500, 500]);
  assert.ok(compiled.sight_obstacles.some((o) => o.default_material === 2));
  assert.equal(compiled.motion_data.layers.flat().length, 1);
  assert.ok(!compiled.material_sectors?.some((o) => o.material === 5));
});
