import test from "node:test";
import assert from "node:assert/strict";
import clipping, { type MultiPolygon } from "polygon-clipping";
import { assembleMovementContour } from "./assemble-movement-contour.ts";
import { preserveMovementBoundary } from "./preserve-movement-boundary.ts";

test("matching fragment endpoints tolerate clipping noise without moving separate placements", () => {
  const unit = 1 / 1048576;
  const fragments: MultiPolygon = [
    [
      [
        [0, 0],
        [10, 0],
        [10, 10],
        [0, 10],
      ],
    ],
    [
      [
        [10 + unit, unit],
        [20, 0],
        [20, 10],
        [10 + unit, 10 + unit],
      ],
    ],
  ];
  const before = structuredClone(fragments);
  const assembled = assembleMovementContour(fragments);
  assert.deepEqual(
    clipping.xor(assembled, [
      [
        [0, 0],
        [20, 0],
        [20, 10],
        [0, 10],
      ],
    ]),
    [],
  );
  assert.deepEqual(assembleMovementContour([...fragments].reverse()), assembled);
  assert.deepEqual(fragments, before);
  const rotate = ([x, y]: [number, number]): [number, number] => [
    (x - y) / Math.SQRT2,
    (x + y) / Math.SQRT2,
  ];
  assert.equal(
    assembleMovementContour(fragments.map((p) => p.map((r) => r.map(rotate)))).length,
    1,
  );
  const detached = structuredClone(fragments);
  detached[1] = detached[1]!.map((ring) => ring.map(([x, y]) => [x + 8 * unit, y]));
  assert.equal(assembleMovementContour(detached).length, 2);
});

test("joining noisy contour fragments does not add rounded corners to their shared outline", () => {
  const unit = 1 / 1048576;
  const boundary: [number, number][] = [
    [-20, -20],
    [60, -20],
    [60, 60],
    [-20, 60],
  ];
  const fragments: MultiPolygon = [
    [
      [
        [0, 0],
        [6, 11.7],
        [5, 39.5],
        [-10, 40],
        [-10, 0],
      ],
    ],
    [
      [
        [6 + unit, 11.7 + 2 * unit],
        [20, 39],
        [5, 39.5],
      ],
    ],
  ];
  const joined = preserveMovementBoundary(boundary, fragments, [], ["wall", "wall"]);
  assert.deepEqual(
    clipping.xor(
      joined.blockers.map((p) => [p]),
      [
        [
          [0, 0],
          [20, 39],
          [-10, 40],
          [-10, 0],
        ],
      ],
    ),
    [],
  );
  const separate = preserveMovementBoundary(boundary, fragments, [], ["first", "second"]);
  assert.equal(separate.blockers.length, 2);
});
