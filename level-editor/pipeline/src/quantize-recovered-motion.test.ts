import test from "node:test";
import assert from "node:assert/strict";
import { quantizeRecoveredMotion } from "./quantize-recovered-motion.ts";
import { polygonArea } from "./recover-ground-gameplay.ts";

test("rounded clearance crossings become valid integer regions instead of cancelling their area", () => {
  const warnings: string[] = [];
  const result = quantizeRecoveredMotion(
    [
      [
        [
          [308, 844],
          [315, 850],
          [314, 850],
          [313, 848],
          [308, 844],
        ],
      ],
    ],
    "clearance",
    warnings,
  );
  assert.ok(result.length > 0);
  assert.ok(polygonArea(result) > 0);
  for (const polygon of result)
    for (const ring of polygon) for (const point of ring) assert.ok(point.every(Number.isInteger));
  assert.ok(warnings.some((w) => w.includes("normalized recovered boundaries")));
  assert.deepEqual(quantizeRecoveredMotion(result, "stable", []), result);
});

test("normalization preserves holes and disconnected regions", () => {
  const regions = [
    [
      [
        [0, 0],
        [10, 0],
        [10, 10],
        [0, 10],
        [0, 0],
      ],
      [
        [2, 2],
        [2, 4],
        [4, 4],
        [4, 2],
        [2, 2],
      ],
    ],
    [
      [
        [20, 0],
        [22, 0],
        [22, 2],
        [20, 2],
        [20, 0],
      ],
    ],
  ] as [number, number][][][];
  const result = quantizeRecoveredMotion(regions, "regions", []);
  assert.equal(result.length, 2);
  assert.equal(result[0]!.length, 2);
  assert.equal(polygonArea(result), 100);
});
