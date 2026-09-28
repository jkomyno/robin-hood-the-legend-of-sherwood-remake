import test from "node:test";
import assert from "node:assert/strict";
import type { Mask } from "../../shared/src/level.ts";
import { encodeMaskBitmap } from "../../shared/src/encode-mask-bitmap.ts";
import { matchRecoveredMask, verifyMaskTranslation } from "./mask-roundtrip.ts";

const mask = (): Mask => ({
  layer: 0,
  mask_type: 4,
  character_polyline: null,
  projectile_polyline: null,
  box_top_left: [10, 20],
  box_size: [2, 1],
  mask_data: encodeMaskBitmap(new Uint8Array([1, 0]), 2, 1),
  obstacle_indices: [],
});

test("view-only masks match by actual pixels despite different empty padding and layer IDs", () => {
  const expected = mask();
  const compiled = { ...mask(), layer: 9, box_size: [1, 1] as [number, number] };
  compiled.mask_data = encodeMaskBitmap(new Uint8Array([1]), 1, 1);
  assert.equal(matchRecoveredMask(expected, [{ ...mask(), box_top_left: [50, 20] }, compiled]), 1);
  assert.throws(() => matchRecoveredMask(expected, [compiled, compiled]), /one compiled/);
  assert.throws(
    () => matchRecoveredMask(expected, [{ ...compiled, mask_type: 5 }]),
    /one compiled/,
  );
  compiled.mask_data = encodeMaskBitmap(new Uint8Array([0]), 1, 1);
  assert.throws(() => matchRecoveredMask(expected, [compiled]), /one compiled/);
});

test("mask comparisons detect boundary, bitmap and obstacle-link regressions", () => {
  const before = mask();
  before.mask_type = 23;
  before.character_polyline = [
    [10, 20],
    [12, 20],
  ];
  before.projectile_polyline = [
    [10, 30],
    [12, 30],
  ];
  before.obstacle_indices = [7];
  assert.equal(matchRecoveredMask(before, [{ ...before, layer: 8, obstacle_indices: [15] }]), 0);
  assert.throws(
    () => matchRecoveredMask(before, [{ ...before, obstacle_indices: [] }]),
    /one compiled/,
  );
  const after: Mask = {
    ...before,
    box_top_left: [42, 20],
    character_polyline: [
      [42, 20],
      [44, 20],
    ],
    projectile_polyline: [
      [42, 30],
      [44, 30],
    ],
  };
  verifyMaskTranslation(before, after, 32);
  assert.throws(() => verifyMaskTranslation(before, { ...after, obstacle_indices: [8] }, 32));
  assert.throws(() =>
    verifyMaskTranslation(
      before,
      { ...after, projectile_polyline: before.projectile_polyline },
      32,
    ),
  );
  assert.throws(() => verifyMaskTranslation(before, { ...after, mask_data: [0] }, 32));
  const view = mask();
  verifyMaskTranslation(view, { ...view, box_top_left: [-22, 20] }, -32);
});
