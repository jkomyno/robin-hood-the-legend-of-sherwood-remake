import test from "node:test";
import assert from "node:assert/strict";
import clipping from "polygon-clipping";
import { partitionProjectionMaterials } from "./partition-projection-materials.ts";
import type { Point, SightObstacle } from "./level.ts";

const square = (low: number, high: number): Point[] => [
  [low, low],
  [high, low],
  [high, high],
  [low, high],
];
test("overlap priority follows authored height then tie precedence across placements", () => {
  const boundary = square(0, 100);
  const base = {
    polygon: boundary,
    defaultMaterial: 2,
    materialIndices: [],
    explicit: true,
    owner: "first",
    priority: 20,
    tiePriority: 3,
  };
  const other = { ...base, defaultMaterial: 4, owner: "second", tiePriority: 4 };
  assert.equal(partitionProjectionMaterials(boundary, [base, other])[0]!.defaultMaterial, 4);
  other.priority = 19;
  assert.equal(partitionProjectionMaterials(boundary, [base, other])[0]!.defaultMaterial, 2);
  other.priority = 20;
  other.tiePriority = 3;
  assert.throws(() => partitionProjectionMaterials(boundary, [base, other]), /conflicting/);
  other.owner = "first";
  assert.equal(partitionProjectionMaterials(boundary, [base, other])[0]!.defaultMaterial, 2);
});
test("a material island leaves a disjoint surrounding receiver with the same height plane", () => {
  const boundary = square(0, 100);
  const pieces = partitionProjectionMaterials(boundary, [
    { polygon: boundary, defaultMaterial: 0, materialIndices: [], explicit: false },
    {
      polygon: square(20, 80),
      defaultMaterial: 4,
      materialIndices: [7, 2],
      explicit: true,
    },
  ]);
  assert.equal(pieces.filter((piece) => piece.explicit).length, 1);
  assert.deepEqual(pieces.find((piece) => piece.explicit)!.materialIndices, [7, 2]);
  const shapes = pieces.map((piece) => [piece.polygon]);
  assert.deepEqual(clipping.xor(clipping.union(shapes[0]!, ...shapes.slice(1)), [boundary]), []);
  for (const [i, shape] of shapes.entries())
    for (const other of shapes.slice(i + 1))
      assert.deepEqual(clipping.intersection(shape, other), []);
  assert.throws(
    () =>
      partitionProjectionMaterials(boundary, [
        { polygon: boundary, defaultMaterial: 2, materialIndices: [], explicit: true },
        { polygon: square(20, 80), defaultMaterial: 4, materialIndices: [], explicit: true },
      ]),
    /conflicting projection materials/,
  );
});

test("explicit receivers leave unsupported parts of a merged boundary uncovered", () => {
  const boundary = square(0, 100);
  const support = {
    polygon: square(20, 80),
    defaultMaterial: 4,
    materialIndices: [],
    explicit: true,
  };
  const pieces = partitionProjectionMaterials(boundary, [support]);
  assert.equal(pieces.length, 1);
  assert.deepEqual(clipping.xor([pieces[0]!.polygon], [support.polygon]), []);
  const implicit = {
    polygon: square(0, 30),
    defaultMaterial: 0,
    materialIndices: [],
    explicit: false,
  };
  const mixed = partitionProjectionMaterials(boundary, [support, implicit]);
  const shapes = mixed.map((piece) => [piece.polygon]);
  assert.deepEqual(
    clipping.xor(
      clipping.union(shapes[0]!, ...shapes.slice(1)),
      clipping.union([support.polygon], [implicit.polygon]),
    ),
    [],
  );
});

test("equivalent region definitions do not conflict merely because their indices differ", () => {
  const boundary = square(0, 100);
  const definition = {
    polygon: boundary,
    defaultMaterial: 2,
    explicit: true,
    materialSignature: "same-placed-regions",
  };
  const pieces = partitionProjectionMaterials(boundary, [
    { ...definition, owner: "first", materialIndices: [3] },
    { ...definition, owner: "second", materialIndices: [9] },
  ]);
  assert.equal(pieces.length, 1);
  assert.deepEqual(pieces[0]!.materialIndices, [3]);
});

test("equivalent native receiving planes retain authored anchors across an overlap", () => {
  const boundary = square(0, 100);
  const anchors: NonNullable<SightObstacle["projection_plane"]> = [
    [0, 0, 20],
    [100, 0, 20],
    [0, 100, 20],
  ];
  const translated: typeof anchors = [
    [1, 0, 20],
    [101, 0, 20],
    [1, 100, 20],
  ];
  const first = {
    polygon: boundary,
    defaultMaterial: 2,
    materialIndices: [],
    explicit: true,
    owner: "wall",
    planePoints: anchors,
  };
  const second = { ...first, owner: "tower", planePoints: translated };
  const pieces = partitionProjectionMaterials(boundary, [first, second]);
  assert.equal(pieces.length, 1);
  assert.deepEqual(pieces[0]!.planePoints, anchors);
  assert.deepEqual(second.planePoints, translated);
  const conflict = { ...second, defaultMaterial: 4 };
  assert.throws(
    () => partitionProjectionMaterials(boundary, [first, conflict]),
    (error) => {
      assert(error instanceof Error);
      assert.match(error.message, /wall and tower/);
      assert(error.cause && typeof error.cause === "object" && "overlap" in error.cause);
      assert.equal(error.cause.overlap, 10000);
      return true;
    },
  );
  second.planePoints = [
    [1, 0, 20],
    [101, 0, 21],
    [1, 100, 20],
  ];
  assert.throws(() => partitionProjectionMaterials(boundary, [first, second]), /conflicting/);
});
