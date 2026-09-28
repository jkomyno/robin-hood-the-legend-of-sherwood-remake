import test from "node:test";
import assert from "node:assert/strict";
import type { Mask } from "../../shared/src/level.ts";
import { encodeMaskBitmap } from "../../shared/src/encode-mask-bitmap.ts";
import { maskSurfaceCoverage } from "./mask-surface-coverage.ts";

const bitmap = (x: number, y: number, rows: string[]): Mask => ({
  layer: 0,
  mask_type: 4,
  character_polyline: null,
  projectile_polyline: null,
  obstacle_indices: [],
  box_top_left: [x, y],
  box_size: [rows[0]!.length, rows.length],
  mask_data: encodeMaskBitmap(Uint8Array.from(rows.join(""), Number), rows[0]!.length, rows.length),
});

test("coverage audit distinguishes interior gaps and reports absolute repair bounds", () => {
  const source = bitmap(-2, 10, ["11111", "11111", "11111", "11111", "11111"]);
  const mesh = bitmap(-2, 10, ["11111", "11111", "11011", "11111", "01111"]);
  assert.deepEqual(maskSurfaceCoverage(source, [mesh]), {
    coveredPixels: 25,
    missingPixels: 2,
    interiorMissingPixels: 1,
    firstMissing: [0, 12],
    missingBounds: [-2, 12, 1, 15],
  });
});

test("coverage audit unions overlapping tiles and ignores extra mesh coverage", () => {
  const source = bitmap(-1, 4, ["111", "101", "111"]);
  const left = bitmap(-2, 3, ["111", "111", "111", "111", "111"]);
  const right = bitmap(0, 4, ["111", "111", "111"]);
  assert.deepEqual(maskSurfaceCoverage(source, [left, right, left]), {
    coveredPixels: 8,
    missingPixels: 0,
    interiorMissingPixels: 0,
    firstMissing: null,
    missingBounds: null,
  });
  assert.equal(maskSurfaceCoverage(source, []).missingPixels, 8);
  assert.equal(maskSurfaceCoverage(source, [bitmap(50, 50, ["1"])]).missingPixels, 8);
});
