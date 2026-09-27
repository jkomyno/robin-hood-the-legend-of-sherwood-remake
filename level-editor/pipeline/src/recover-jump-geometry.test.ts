import test from "node:test";
import assert from "node:assert/strict";
import { jumpAssetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { recoverJumpGeometry, recoverJumpSegment } from "./recover-jump-geometry.ts";

test("split jump recovery retains each home zone and a shared socket in different asset frames", () => {
  const { document, assets } = jumpAssetCompilerFixture();
  const geometry = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const source = {
    motion_data: geometry.motion_data,
    jump_zones: geometry.jump_zones!,
    jump_line_pairs: geometry.jump_line_pairs!,
  };
  const low = recoverJumpSegment(
    0,
    source,
    0,
    "low-frame",
    ([x, y, z]) => [x - 300, y - 300, z],
    (zone) => (zone.layer ? 100 : 0),
  );
  const high = recoverJumpSegment(
    1,
    source,
    0,
    "high-frame",
    ([x, y, z]) => [x - 1000, y - 900, z - 100],
    (zone) => (zone.layer ? 100 : 0),
  );
  assert.equal(low.segment.edge.zone, low.zone.id);
  assert.equal(high.segment.edge.zone, high.zone.id);
  assert.equal(low.zone.helperNeeded, true);
  assert.equal(high.zone.helperNeeded, false);
  assert.deepEqual(
    low.segment.join.map((n, i) => n + [300, 300, 0][i]!),
    high.segment.join.map((n, i) => n + [1000, 900, 100][i]!),
  );
  assert.notDeepEqual(low.segment.edge.a, high.segment.edge.a);
});

test("jump recovery reconstructs local height, helper flags and crossed zone references", () => {
  const { hut, document, assets } = jumpAssetCompilerFixture();
  const first = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const source = {
    motion_data: first.motion_data,
    jump_zones: first.jump_zones!,
    jump_line_pairs: first.jump_line_pairs!,
  };
  const recovered = recoverJumpGeometry(
    source,
    0,
    "building-999",
    ([x, y, z]) => [x - 300, y - 300, z],
    (zone) => (zone.layer === 0 ? 0 : 100),
  );
  hut.gameplay!.jumpZones = recovered.zones;
  hut.gameplay!.jumpPairs = [recovered.pair];
  const result = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  for (const key of ["jump_zones", "jump_line_pairs"] as const)
    assert.deepEqual(result[key], first[key]);
  source.jump_line_pairs[0]!.line1.jump_zone_index = 99;
  assert.throws(
    () =>
      recoverJumpGeometry(
        source,
        0,
        "building-999",
        (p) => p,
        () => 0,
      ),
    /Missing jump zone/,
  );
});
