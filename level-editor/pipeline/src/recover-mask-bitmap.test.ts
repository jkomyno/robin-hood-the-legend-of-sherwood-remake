import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { Mask } from "../../shared/src/level.ts";
import { encodeMaskBitmap } from "../../shared/src/encode-mask-bitmap.ts";
import { decodeRecoveryMask, recoveryMaskRectangles } from "./recover-mask-bitmap.ts";

test("recovery decodes native cross-language bitmap fixtures", () => {
  const cases: { width: number; height: number; pixels: string; encoded: number[] }[] = JSON.parse(
    readFileSync(
      new URL(
        "../../../crates/robin_engine/tests/fixtures/compiled-mask-bitmaps.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  for (const fixture of cases)
    assert.equal(
      decodeRecoveryMask({
        box_size: [fixture.width, fixture.height],
        mask_data: fixture.encoded,
      }).join(""),
      fixture.pixels,
    );
});

test("recovery merges vertical runs without filling holes or overlapping coverage", () => {
  const rows = ["00000000", "01111110", "01000010", "01000010", "00000000", "01000010", "01111110"];
  const mask: Mask = {
    layer: 0,
    mask_type: 4,
    character_polyline: null,
    projectile_polyline: null,
    obstacle_indices: [],
    box_top_left: [-10, 20],
    box_size: [8, rows.length],
    mask_data: encodeMaskBitmap(Uint8Array.from(rows.join(""), Number), 8, rows.length),
  };
  const rectangles = recoveryMaskRectangles(mask);
  assert.equal(rectangles.length, 6);
  assert.deepEqual(rectangles[1], { left: -9, top: 22, right: -8, bottom: 24 });
  const pixels = new Uint8Array(8 * rows.length);
  for (const rectangle of rectangles)
    for (let y = rectangle.top; y < rectangle.bottom; y++)
      for (let x = rectangle.left; x < rectangle.right; x++) pixels[(y - 20) * 8 + x + 10]!++;
  assert.equal(pixels.join(""), rows.join(""));
});

test("recovery accepts transparent trailing blocks and clips final byte padding", () => {
  assert.equal(
    decodeRecoveryMask({ box_size: [9, 2], mask_data: [2, 129, 255, 0] }).join(""),
    "111111110000000000",
  );
  assert.equal(
    decodeRecoveryMask({ box_size: [9, 1], mask_data: [2, 130, 255] }).join(""),
    "111111111",
  );
});

test("recovery rejects malformed input instead of silently losing pixels", () => {
  for (const data of [
    [],
    [3, 129, 255],
    [1, 129],
    [1, 0],
    [2, 130, 255],
    [0, 0],
    [2, 1, 256],
    [2, 1, 0.5],
  ])
    assert.throws(() => decodeRecoveryMask({ box_size: [8, 1], mask_data: data }));
  for (const size of [0, -1, 1.5, 32768, NaN])
    assert.throws(() => decodeRecoveryMask({ box_size: [size, 1], mask_data: [] }));
});
