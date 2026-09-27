import test from "node:test";
import assert from "node:assert/strict";
import { quantizeGeneratedMotionPolygon } from "./motion-quantization.ts";

test("generated subpixel fragments collapse explicitly without emitting degenerate motion areas", () => {
  const warnings: string[] = [];
  assert.equal(
    quantizeGeneratedMotionPolygon(
      [
        [
          [307, 1074],
          [309, 1069],
          [307.01, 1074.01],
          [307, 1074],
        ],
      ],
      Math.round,
      "test layer",
      warnings,
    ),
    null,
  );
  assert.equal(warnings.length, 1);
  assert.match(warnings[0]!, /region.*zero area/);
});

test("collapsed holes are reported while representable half-pixel triangles survive", () => {
  const warnings: string[] = [];
  const result = quantizeGeneratedMotionPolygon(
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
        [2.1, 2],
        [2.1, 3],
        [2, 2],
      ],
      [
        [4, 4],
        [5, 4],
        [4, 5],
        [4, 4],
      ],
    ],
    Math.round,
    "test layer",
    warnings,
  )!;
  assert.equal(result.length, 2);
  assert.deepEqual(result[1], [
    [4, 4],
    [5, 4],
    [4, 5],
    [4, 4],
  ]);
  assert.match(warnings[0]!, /hole.*zero area/);
});

test("signed-area cancellation is not treated as a collinear collapse", () => {
  const bowtie = [
    [
      [0, 0],
      [4, 4],
      [0, 4],
      [4, 0],
      [0, 0],
    ],
  ] as [number, number][][];
  const warnings: string[] = [];
  assert.deepEqual(
    quantizeGeneratedMotionPolygon(bowtie, Math.round, "invalid ring", warnings),
    bowtie,
  );
  assert.equal(warnings.length, 0);
});

test("zero-width backtracking traces are reported as collapsed regions", () => {
  const warnings: string[] = [];
  assert.equal(
    quantizeGeneratedMotionPolygon(
      [
        [
          [771, 2418],
          [783, 2434],
          [806, 2429],
          [783, 2434],
          [771, 2418],
        ],
      ],
      Math.round,
      "backtracking fragment",
      warnings,
    ),
    null,
  );
  assert.equal(warnings.length, 1);
});
