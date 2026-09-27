import { test } from "node:test";
import assert from "node:assert/strict";
import { compareJumpGeometry, type JumpGeometry } from "./compare-jump-geometry.ts";

function fixture(): JumpGeometry {
  return {
    jump_zones: [
      {
        polygon: {
          points: [
            [0, 0],
            [0, 10],
            [10, 10],
            [10, 0],
          ],
        },
        helper_needed: false,
      },
      {
        polygon: {
          points: [
            [20, 0],
            [20, 10],
            [30, 10],
            [30, 0],
          ],
        },
        helper_needed: true,
      },
    ],
    jump_line_pairs: [
      {
        line1: { point_a: [0, 0, 0], point_b: [0, 10, 0], jump_zone_index: 1 },
        line2: { point_a: [20, 0, 50], point_b: [20, 10, 50], jump_zone_index: 0 },
        jump_long: true,
      },
    ],
  };
}

test("jump comparison permits rebuilt indices and equivalent polygon winding", () => {
  const source = fixture(),
    compiled = fixture();
  compiled.jump_zones.reverse();
  for (const zone of compiled.jump_zones) {
    zone.polygon.points.reverse();
    zone.polygon.points.push(zone.polygon.points.shift()!);
  }
  compiled.jump_line_pairs[0]!.line1.jump_zone_index = 0;
  compiled.jump_line_pairs[0]!.line2.jump_zone_index = 1;
  assert.equal(compareJumpGeometry(source, compiled).equivalent, true);
});

test("jump comparison detects height, helper, topology, and multiplicity changes", () => {
  for (const alter of [
    (d: JumpGeometry) => {
      d.jump_line_pairs[0]!.line1.point_a[2] = 1;
    },
    (d: JumpGeometry) => {
      d.jump_zones[0]!.helper_needed = true;
    },
    (d: JumpGeometry) => {
      const p = d.jump_zones[0]!.polygon.points;
      [p[1], p[2]] = [p[2]!, p[1]!];
    },
    (d: JumpGeometry) => {
      d.jump_line_pairs.push(structuredClone(d.jump_line_pairs[0]!));
    },
  ]) {
    const compiled = fixture();
    alter(compiled);
    assert.equal(compareJumpGeometry(fixture(), compiled).equivalent, false);
  }
});
