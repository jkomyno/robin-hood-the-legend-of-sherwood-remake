import test from "node:test";
import assert from "node:assert/strict";
import type { ProtoLevel } from "@rle/shared";
import { clipLevel } from "./clip.ts";

test("jump extraction retains elevation and remaps both zones even across the crop boundary", () => {
  const zones = [500, 100, 900].map((x) => ({
    polygon: {
      points: [
        [x, 0],
        [x + 20, 0],
        [x + 20, 20],
        [x, 20],
      ],
    },
    sector: x,
    layer: 0,
    helper_needed: false,
  }));
  const level = {
    sight_obstacles: [],
    motion_data: { layers: [] },
    lifts: [],
    material_sectors: [],
    masks: [],
    jump_zones: zones,
    jump_line_pairs: [
      {
        line1: { point_a: [105, 10, 70], point_b: [115, 10, 80], jump_zone_index: 2 },
        line2: { point_a: [905, 10, 0], point_b: [915, 10, 0], jump_zone_index: 1 },
        jump_long: true,
      },
    ],
  } as unknown as ProtoLevel;
  const result = clipLevel(level, [100, 0, 20, 20]);
  assert.equal(result.jump_zones.length, 2);
  assert.deepEqual(result.jump_line_pairs[0], {
    line1: { point_a: [5, 10, 70], point_b: [15, 10, 80], jump_zone_index: 1 },
    line2: { point_a: [805, 10, 0], point_b: [815, 10, 0], jump_zone_index: 0 },
    jump_long: true,
  });
  level.jump_line_pairs[0]!.line2.jump_zone_index = 99;
  assert.throws(() => clipLevel(level, [100, 0, 20, 20]), /missing zone 99/);
});
