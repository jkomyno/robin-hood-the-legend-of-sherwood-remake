import test from "node:test";
import assert from "node:assert/strict";
import type { SightObstacle } from "../../shared/src/level.ts";
import { compareReceivingPlaneAnchors } from "./compare-receiving-plane-anchors.ts";

const source: SightObstacle = {
  points: [
    [10, 20],
    [110, 20],
    [110, 120],
  ].map(([x, y]) => ({
    x: x!,
    y: y!,
    z_top: 200.001,
    z_bottom: 0,
  })),
  projection_area: [7, 1],
  opaque: false,
  solid: false,
  mouse: true,
  show_shadow_polygon: false,
  default_material: 2,
  material_indices: [],
};

test("anchor audit preserves native order and float32 values across export frames", () => {
  const compiled: SightObstacle = {
    ...source,
    projection_area: [18, 3],
    projection_plane: [
      [100, 0, 200.001],
      [100, 100, 200.001],
      [0, 0, 200.001],
    ],
  };
  assert.equal(compareReceivingPlaneAnchors([source], [compiled], [10, 20]).allMatch, true);
  compiled.projection_plane![0][2] += 1e-8;
  assert.equal(compareReceivingPlaneAnchors([source], [compiled], [10, 20]).allMatch, true);
  compiled.projection_plane![0][2] += 0.00002;
  assert.equal(compareReceivingPlaneAnchors([source], [compiled], [10, 20]).allMatch, false);
  compiled.projection_plane![0][2] = 200.001;
  compiled.projection_plane!.reverse();
  assert.equal(compareReceivingPlaneAnchors([source], [compiled], [10, 20]).allMatch, false);
});

test("anchor audit reports missing metadata and rejects nonfinite native anchors", () => {
  assert.deepEqual(compareReceivingPlaneAnchors([source], [source]), {
    compared: 0,
    unanchored: 1,
    allMatch: false,
    differences: [],
  });
  const compiled: SightObstacle = {
    ...source,
    projection_plane: [
      [110, 20, 200.001],
      [110, 120, 200.001],
      [10, 20, 1e100],
    ],
  };
  assert.throws(() => compareReceivingPlaneAnchors([source], [compiled]), /native precision/);
});
