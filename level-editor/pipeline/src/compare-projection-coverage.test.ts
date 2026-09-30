import test from "node:test";
import assert from "node:assert/strict";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { multiPlaneRegionCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compareProjectionCoverage } from "./compare-projection-coverage.ts";

function fixture() {
  const { document, assets } = multiPlaneRegionCompilerFixture();
  return compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
}

test("projection coverage ignores subdivision while preserving height and receiving rules", () => {
  const before = fixture(),
    after = structuredClone(before),
    quad = after.sight_obstacles.shift()!;
  assert.equal(quad.points.length, 4);
  after.sight_obstacles.push(
    { ...quad, points: [quad.points[0]!, quad.points[1]!, quad.points[2]!] },
    { ...quad, points: [quad.points[0]!, quad.points[2]!, quad.points[3]!] },
  );
  assert.equal(compareProjectionCoverage(before, after).equal, true);
  after.sight_obstacles.pop();
  const missing = compareProjectionCoverage(before, after);
  assert.equal(missing.equal, false);
  assert.ok(missing.differences.some((d) => d.removedArea > 0));
});

test("projection coverage detects changed material, height, flags and receiving bindings", () => {
  const before = fixture();
  for (const change of [
    (g: typeof before) => {
      g.sight_obstacles[0]!.default_material += 1;
    },
    (g: typeof before) => {
      for (const p of g.sight_obstacles[0]!.points) {
        p.y += 1;
        p.z_top += 1;
        p.z_bottom += 1;
      }
    },
    (g: typeof before) => {
      g.sight_obstacles[0]!.mouse = false;
    },
  ]) {
    const after = structuredClone(before);
    change(after);
    assert.equal(compareProjectionCoverage(before, after).equal, false);
  }
  const invalid = structuredClone(before);
  invalid.sight_obstacles[0]!.projection_area = [999, 0];
  assert.throws(() => compareProjectionCoverage(before, invalid), /invalid receiving area/);
  invalid.sight_obstacles[0]!.projection_area = before.sight_obstacles[0]!.projection_area;
  invalid.sight_obstacles[0]!.material_indices = [999];
  assert.throws(() => compareProjectionCoverage(before, invalid), /invalid material reference/);
});

test("projection coverage resolves rebuilt material references and counts blocker constructor slots", () => {
  const before = fixture(),
    layer = before.motion_data.layers.findIndex((l) => l.length);
  before.material_sectors = [
    {
      material: 2,
      polygon: {
        points: [
          [0, 0],
          [10, 0],
          [10, 10],
        ],
      },
    },
    {
      material: 3,
      polygon: {
        points: [
          [20, 0],
          [30, 0],
          [30, 10],
        ],
      },
    },
  ];
  before.sight_obstacles[0]!.material_indices = [0];
  const dummy = structuredClone(before.motion_data.layers[layer]![0]!);
  dummy.polygon.points = [
    [1000, 1000],
    [1100, 1000],
    [1100, 1100],
    [1000, 1100],
  ];
  dummy.obstacles = [
    {
      state_id: 0,
      polygon: {
        points: [
          [1020, 1020],
          [1030, 1020],
          [1030, 1030],
        ],
      },
    },
  ];
  before.motion_data.layers[layer]!.unshift(dummy);
  for (const o of before.sight_obstacles) o.projection_area = [2, layer];
  const after = structuredClone(before);
  after.motion_data.layers[layer]!.push(after.motion_data.layers[layer]!.shift()!);
  for (const o of after.sight_obstacles) o.projection_area = [0, layer];
  after.material_sectors!.reverse();
  after.sight_obstacles[0]!.material_indices = [1];
  assert.equal(compareProjectionCoverage(before, after).equal, true);
  after.motion_data.layers[layer]!.push(structuredClone(after.motion_data.layers[layer]![0]!));
  assert.throws(() => compareProjectionCoverage(before, after), /ambiguous receiving areas/);
});
