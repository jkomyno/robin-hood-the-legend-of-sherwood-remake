import test from "node:test";
import assert from "node:assert/strict";
import type { Mask } from "../../shared/src/level.ts";
import { encodeMaskBitmap } from "../../shared/src/encode-mask-bitmap.ts";
import { matchRecoveredMasks, verifyMaskTranslation } from "./mask-roundtrip.ts";
import { rasterizeMaskGeometry } from "../../shared/src/compile-mask-geometry.ts";

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
  assert.deepEqual(
    matchRecoveredMasks(expected, [{ ...mask(), box_top_left: [50, 20] }, compiled]),
    [1],
  );
  assert.throws(() => matchRecoveredMasks(expected, [compiled, compiled]), /overlapping/);
  assert.throws(
    () => matchRecoveredMasks(expected, [{ ...compiled, mask_type: 5 }]),
    /complete compiled/,
  );
  compiled.mask_data = encodeMaskBitmap(new Uint8Array([0]), 1, 1);
  assert.throws(() => matchRecoveredMasks(expected, [compiled]), /complete compiled/);
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
  assert.deepEqual(
    matchRecoveredMasks(before, [{ ...before, layer: 8, obstacle_indices: [15] }]),
    [0],
  );
  assert.throws(
    () => matchRecoveredMasks(before, [{ ...before, obstacle_indices: [] }]),
    /complete compiled/,
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

test("large recovered masks match every compiler tile without accepting gaps or mixed bindings", () => {
  for (const [width, height] of [
    [2050, 1],
    [1, 2050],
  ] as const) {
    const expected: Mask = {
      ...mask(),
      mask_type: 22,
      projectile_polyline: [],
      obstacle_indices: [3],
      box_top_left: [0, 0],
      box_size: [width, height],
      mask_data: encodeMaskBitmap(new Uint8Array(width * height).fill(1), width, height),
    };
    const tiles = rasterizeMaskGeometry(
      [
        [
          [0, 0, 0],
          [width, 0, 0],
          [width, height, 0],
        ],
        [
          [0, 0, 0],
          [width, height, 0],
          [0, height, 0],
        ],
      ],
      { ...expected, layer: 7, obstacle_indices: [9] },
    );
    assert.equal(tiles.length, 3);
    assert.deepEqual(matchRecoveredMasks(expected, tiles), [0, 1, 2]);
    assert.throws(() => matchRecoveredMasks(expected, tiles.slice(0, 2)), /complete compiled/);
    assert.throws(() => matchRecoveredMasks(expected, [...tiles, tiles[0]!]), /overlapping/);
    assert.throws(
      () => matchRecoveredMasks(expected, [tiles[0]!, { ...tiles[1]!, layer: 8 }, tiles[2]!]),
      /receiving layers/,
    );
    assert.throws(
      () =>
        matchRecoveredMasks(expected, [
          tiles[0]!,
          { ...tiles[1]!, obstacle_indices: [10] },
          tiles[2]!,
        ]),
      /obstacle links/,
    );
    const broken = structuredClone(tiles);
    const pixels = new Uint8Array(1024).fill(1);
    pixels[1023] = 0;
    broken[0]!.mask_data = encodeMaskBitmap(pixels, ...broken[0]!.box_size);
    assert.throws(() => matchRecoveredMasks(expected, broken), /complete compiled/);
  }
});
