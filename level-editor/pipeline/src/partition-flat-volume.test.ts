import assert from "node:assert/strict";
import test from "node:test";
import { partitionFlatVolume } from "./partition-flat-volume.ts";
import type { SightObstacle } from "@rle/shared";

const source: SightObstacle = {
  points: [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100],
  ].map(([x, y]) => ({ x: x!, y: y!, z_bottom: 0, z_top: 50 })),
  opaque: true,
  solid: true,
  mouse: true,
  show_shadow_polygon: true,
  default_material: 0,
  material_indices: [],
  projection_area: null,
};
const seamA = { edge: 0, fraction: 0.4 },
  seamB = { edge: 2, fraction: 0.6 };
test("explicit seams retain footprint, flags, heights and independent points", () => {
  const pieces = partitionFlatVolume(source, [
    [0, seamA, seamB, 3],
    [seamA, 1, 2, seamB],
  ]);
  assert.deepEqual(
    pieces.map((s) => s.points.map((p) => [p.x, p.y])),
    [
      [
        [0, 0],
        [40, 0],
        [40, 100],
        [0, 100],
      ],
      [
        [40, 0],
        [100, 0],
        [100, 100],
        [40, 100],
      ],
    ],
  );
  for (const piece of pieces) {
    assert.equal(piece.solid, true);
    assert(piece.points.every((p) => p.z_bottom === 0 && p.z_top === 50));
  }
  pieces[0]!.points[0]!.x = 99;
  assert.equal(source.points[0]!.x, 0);
});
test("missing coverage, overlap and nonflat planes cannot become approved partitions", () => {
  assert.throws(
    () =>
      partitionFlatVolume(source, [
        [0, seamA, seamB, 3],
        [1, 2, seamB],
      ]),
    /footprint/,
  );
  assert.throws(
    () =>
      partitionFlatVolume(source, [
        [0, 1, 2, 3],
        [0, 1, 2],
      ]),
    /overlap/,
  );
  const slope = structuredClone(source);
  slope.points[1]!.z_top = 51;
  assert.throws(
    () =>
      partitionFlatVolume(slope, [
        [0, 1, 2],
        [0, 2, 3],
      ]),
    /constant/,
  );
  assert.throws(
    () =>
      partitionFlatVolume({ ...source, projection_area: [1, 0] }, [
        [0, 1, 2],
        [0, 2, 3],
      ]),
    /separate/,
  );
  assert.throws(
    () =>
      partitionFlatVolume(source, [
        [0, { edge: 0, fraction: 2 }, 3],
        [1, 2, 3],
      ]),
    /fraction/,
  );
});
