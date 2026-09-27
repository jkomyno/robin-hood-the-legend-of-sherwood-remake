import test from "node:test";
import assert from "node:assert/strict";
import { jumpEdgeOwners } from "./jump-edge-ownership.ts";
import type { JumpLine, SightObstacle } from "../../shared/src/level.ts";

test("a split wall assigns a jump edge only to the containing part", () => {
  const shape = (left: number): SightObstacle => ({
    points: [
      [left, 0],
      [left + 50, 0],
      [left + 50, 50],
      [left, 50],
    ].map(([x, y]) => ({ x: x!, y: y!, z_bottom: 0, z_top: 20 })),
    projection_area: null,
    solid: true,
    opaque: true,
    mouse: true,
    show_shadow_polygon: false,
    default_material: 0,
    material_indices: [],
  });
  const north = { asset: "north", shape: shape(0) },
    south = { asset: "south", shape: shape(50) };
  const line: JumpLine = { point_a: [10, 0, 20], point_b: [40, 0, 20], jump_zone_index: 0 };
  assert.deepEqual(
    jumpEdgeOwners(line, [north, south], (o) => o.shape),
    [north],
  );
  line.point_b[0] = 60;
  assert.deepEqual(
    jumpEdgeOwners(line, [north, south], (o) => o.shape),
    [],
  );
  const secondPlane = { ...south, asset: north.asset };
  assert.deepEqual(
    jumpEdgeOwners(line, [north, secondPlane], (o) => o.shape),
    [north, secondPlane],
  );
  secondPlane.shape = shape(55);
  assert.deepEqual(
    jumpEdgeOwners(line, [north, secondPlane], (o) => o.shape),
    [],
  );
});
