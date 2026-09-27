import test from "node:test";
import assert from "node:assert/strict";
import { normalizeGeneratedMotion } from "./normalize-generated-motion.ts";

test("a generated crossing with cancelling signed area becomes usable movement regions", () => {
  const warnings: string[] = [];
  const regions = normalizeGeneratedMotion(
    [
      [
        [
          [2031, 1875],
          [2039, 1885],
          [2032, 1876],
          [2035, 1881],
          [2031, 1875],
        ],
      ],
    ],
    "Generated intersection",
    warnings,
  );
  assert.ok(regions.length > 0);
  for (const region of regions) {
    assert.ok(region[0]!.length >= 4);
    assert.ok(region.flat().every((p) => p.every(Number.isInteger)));
    const ring = region[0]!;
    const area = ring.reduce((sum, p, i) => {
      const q = ring[(i + 1) % ring.length]!;
      return sum + p[0] * q[1] - p[1] * q[0];
    }, 0);
    assert.notEqual(area, 0);
  }
  assert.ok(warnings.some((w) => w.includes("normalized")));
});
