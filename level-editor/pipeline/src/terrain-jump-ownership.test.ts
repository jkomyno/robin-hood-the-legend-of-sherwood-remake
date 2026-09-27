import test from "node:test";
import assert from "node:assert/strict";
import { terrainOwnsJump } from "./terrain-jump-ownership.ts";
import type { JumpLinePair, JumpZone } from "../../shared/src/level.ts";
import type { RecoveredSurface } from "./recovered-gameplay-definition.ts";

test("ground jumps belong to terrain only across retained terrain exclusions", () => {
  const pair: JumpLinePair = {
    jump_long: false,
    line1: { point_a: [20, 40, 0], point_b: [20, 60, 0], jump_zone_index: 0 },
    line2: { point_a: [80, 40, 0], point_b: [80, 60, 0], jump_zone_index: 1 },
  };
  const zones: JumpZone[] = [7, 9].map((sector) => ({
    sector,
    layer: 0,
    helper_needed: false,
    polygon: { points: [] },
  }));
  const surface = (x: number, right: number): RecoveredSurface => ({
    id: `terrain-${x}`,
    node: "$root",
    vertices: [
      [x, 0, 0],
      [right, 0, 0],
      [right, 100, 0],
      [x, 100, 0],
    ],
    holes: [],
  });
  const ground = [surface(0, 40), surface(60, 100)];
  assert.equal(terrainOwnsJump(pair, zones, new Set([7, 9]), ground), true);
  assert.equal(
    terrainOwnsJump(pair, zones, new Set([7, 9]), ground, [
      [
        [
          [32, 40],
          [35, 40],
          [35, 60],
          [32, 60],
        ],
      ],
    ]),
    false,
  );
  // Filling the gap for a placed object's own blocker transfers ownership away from terrain.
  assert.equal(terrainOwnsJump(pair, zones, new Set([7, 9]), [surface(0, 100)]), false);
  assert.equal(terrainOwnsJump(pair, zones, new Set([7]), ground), false);
  assert.equal(terrainOwnsJump(pair, zones, new Set([7, 9]), [ground[0]!]), false);
  pair.line1.point_a[2] = 10;
  assert.equal(terrainOwnsJump(pair, zones, new Set([7, 9]), ground), false);
});
