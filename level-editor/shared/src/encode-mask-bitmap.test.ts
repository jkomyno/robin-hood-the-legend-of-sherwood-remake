import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { encodeMaskBitmap } from "./encode-mask-bitmap.ts";

test("native mask bitmap fixtures are generated from their complete binary coverage", () => {
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
    assert.deepEqual(
      encodeMaskBitmap(Uint8Array.from(fixture.pixels, Number), fixture.width, fixture.height),
      fixture.encoded,
    );
});

test("mask encoding rejects inconsistent dimensions, nonbinary coverage and overflowing rows", () => {
  assert.throws(() => encodeMaskBitmap(new Uint8Array(2), 3, 1), /dimensions/);
  assert.throws(() => encodeMaskBitmap(new Uint8Array([2]), 1, 1), /binary/);
  assert.throws(() => encodeMaskBitmap(new Uint8Array(), 0, 1), /dimensions/);
  const noise = Uint8Array.from({ length: 4096 }, (_, i) => ((i >> 3) >> (7 - (i & 7))) & 1);
  assert.throws(() => encodeMaskBitmap(noise, 4096, 1), /narrower tiles/);
});
