import test from "node:test";
import assert from "node:assert/strict";
import clipping, { type MultiPolygon } from "polygon-clipping";
import { closedPolygon, polygonArea, recoverGroundGameplay } from "./recover-ground-gameplay.ts";
import type { Point } from "@rle/shared";
import { preserveMovementBoundary } from "../../shared/src/preserve-movement-boundary.ts";
import { partitionMovementObstacles } from "../../shared/src/partition-movement-obstacles.ts";

test("boundary recovery reassembles crossing exclusions without inventing off-map asset collision", () => {
  const boundary: Point[] = [
    [0, 0],
    [100, 0],
    [100, 70],
  ];
  const obstacle: Point[] = [
    [0, -10],
    [110, -10],
    [110, 76],
    [0, -1],
  ];
  const recovered = recoverGroundGameplay(
    [{ polygon: { points: boundary }, obstacles: [{ polygon: { points: obstacle } }] }],
    [
      {
        asset: "wall",
        node: "body",
        footprint: [
          [40, -30],
          [60, -30],
          [60, 90],
          [40, 90],
        ],
      },
    ],
    true,
  );
  const section = recovered.sections[0]!;
  assert.deepEqual(section.movementBoundary, boundary);
  assert(
    recovered.blockers[0]!.regions.flat(2).every(
      ([x, y]) => x >= 40 && x <= 60 && y >= -10 && y <= 76,
    ),
  );
  const assembled = preserveMovementBoundary(
    section.movementBoundary,
    [
      ...section.movementObstacles
        .flatMap((region) => partitionMovementObstacles(region, true))
        .map((p) => [p]),
      ...recovered.blockers.flatMap((b) => b.regions),
    ],
    [],
  );
  assert.deepEqual(assembled.polygon, boundary);
  assert.equal(assembled.blockers.length, 1);
  assert.deepEqual(clipping.xor([obstacle], [assembled.blockers[0]!]), []);
});

test("touching ground regions retain independent topology and per-region fidelity", () => {
  const areas = [0, 100].map((x) => ({
    polygon: {
      points: [
        [x, 0],
        [x + 100, 0],
        [x + 100, 100],
        [x, 100],
      ] as Point[],
    },
    obstacles: [],
  }));
  const recovered = recoverGroundGameplay(areas, []);
  assert.equal(recovered.sections.length, 2);
  assert.notEqual(recovered.sections[0]!.navigationRegion, recovered.sections[1]!.navigationRegion);
  assert.deepEqual(
    recovered.sections.map((s) => s.differenceArea),
    [0, 0],
  );
  assert.deepEqual(
    recovered.sections.map((s) => polygonArea(s.terrain)),
    [10000, 10000],
  );
  assert.equal(recovered.differenceArea, 0);
});

test("ground recovery transfers building cutouts to assets without losing terrain holes", () => {
  const rectangle = (x: number, y: number, w: number, h: number): Point[] => [
    [x, y],
    [x + w, y],
    [x + w, y + h],
    [x, y + h],
  ];
  const original = [
    {
      polygon: { points: rectangle(0, 0, 100, 100) },
      obstacles: [
        { polygon: { points: rectangle(40, 40, 20, 20) } },
        { polygon: { points: rectangle(10, 10, 10, 10) } },
      ],
    },
  ];
  const result = recoverGroundGameplay(original, [
    { asset: "house", node: "body", footprint: rectangle(35, 35, 30, 30) },
    { asset: "unrelated", node: "body", footprint: rectangle(500, 500, 30, 30) },
  ]);
  assert.equal(result.blockers.length, 1);
  assert.equal(result.sourceArea, 9500);
  assert.equal(result.differenceArea, 0);
  assert.equal(polygonArea(result.terrain), 9900);
  assert.equal(polygonArea(result.blockers[0]!.regions), 400);
  const moved: MultiPolygon = result.blockers[0]!.regions.map((p) =>
    p.map((ring) => ring.map(([x, y]) => [x + 30, y])),
  );
  const assembled = clipping.difference(result.terrain, moved);
  assert.equal(
    polygonArea(clipping.intersection(assembled, closedPolygon(rectangle(40, 40, 20, 20)))),
    400,
  );
  assert.equal(
    polygonArea(clipping.intersection(assembled, closedPolygon(rectangle(70, 40, 20, 20)))),
    0,
  );
  assert.equal(
    polygonArea(clipping.intersection(assembled, closedPolygon(rectangle(10, 10, 10, 10)))),
    0,
  );
});

test("fractional ownership cuts reconstruct the ground without separately rounding terrain and blockers", () => {
  const recovered = recoverGroundGameplay(
    [
      {
        polygon: {
          points: [
            [0, 0],
            [100, 0],
            [100, 100],
            [0, 100],
          ],
        },
        obstacles: [
          {
            polygon: {
              points: [
                [10, 10],
                [90, 70],
                [90, 90],
                [10, 90],
              ],
            },
          },
        ],
      },
    ],
    [
      {
        asset: "wall",
        node: "body",
        footprint: [
          [0, 0],
          [45.3, 0],
          [45.3, 100],
          [0, 100],
        ],
      },
    ],
  );
  assert.ok(recovered.differenceArea < 0.0001);
  assert.equal(recovered.coordinateGrid, 1 / 1048576);
  assert.ok(
    recovered.blockers.some((b) =>
      b.regions.some((p) => p.some((r) => r.some((v) => v.some((n) => !Number.isInteger(n))))),
    ),
  );
});

test("ground recovery rejects empty movement instead of inventing a floor", () => {
  assert.throws(() => recoverGroundGameplay([], []), /No authored ground/);
  const points: Point[] = [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100],
  ];
  assert.throws(
    () =>
      recoverGroundGameplay([{ polygon: { points }, obstacles: [{ polygon: { points } }] }], []),
    /no walkable space/,
  );
});

test("overlapping ground exclusions preserve the narrow corridor between clipped boundaries", () => {
  const area = {
    polygon: {
      points: [
        [2, 957],
        [610, 1],
        [1280, 564],
      ] as Point[],
    },
    obstacles: [
      [
        [1208, 549],
        [1200, 544],
        [1207, 539],
      ],
      [
        [1204.5413, 544.4413000000001],
        [1179.5272, 436.56305998],
        [1276.5056, 498.79459700000007],
      ],
      [
        [1320.358, 595.3621],
        [1204.5215, 545.18443],
        [1276.7925, 499.871797],
      ],
    ].map((points) => ({ polygon: { points: points as Point[] } })),
  };
  const recovered = recoverGroundGameplay([area], []);
  assert.ok(recovered.differenceArea < 0.001, `lost corridor area: ${recovered.differenceArea}`);
  assert.ok(Math.abs(recovered.reconstructedArea - recovered.sourceArea) < 0.001);
});

test("a raised projection's ground exclusion moves with its owner rather than remaining in terrain", () => {
  const boundary: Point[] = [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100],
  ];
  const footprint: Point[] = [
    [20, 20],
    [40, 20],
    [40, 40],
    [20, 40],
  ];
  const recovered = recoverGroundGameplay(
    [{ polygon: { points: boundary }, obstacles: [{ polygon: { points: footprint } }] }],
    [{ asset: "platform", node: "deck", footprint }],
  );
  assert.equal(recovered.differenceArea, 0);
  assert.equal(polygonArea(recovered.terrain), 10000);
  assert.equal(polygonArea(recovered.blockers[0]!.regions), 400);
  const moved = recovered.blockers[0]!.regions.map((p) =>
    p.map((r) => r.map(([x, y]): Point => [x + 40, y])),
  );
  const assembled = clipping.difference(recovered.terrain, moved);
  assert.equal(polygonArea(clipping.intersection(assembled, closedPolygon(footprint))), 400);
  assert.equal(polygonArea(clipping.intersection(assembled, moved)), 0);
});

test("recovered cutouts cannot extend terrain past its authored outer boundary", () => {
  const boundary: Point[] = [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100],
  ];
  const footprint: Point[] = [
    [80, 20],
    [120, 20],
    [120, 40],
    [80, 40],
  ];
  const recovered = recoverGroundGameplay(
    [{ polygon: { points: boundary }, obstacles: [{ polygon: { points: footprint } }] }],
    [{ asset: "edge-platform", node: "deck", footprint }],
  );
  assert.equal(polygonArea(recovered.terrain), 10000);
  assert.equal(recovered.differenceArea, 0);
  assert.equal(polygonArea(clipping.difference(recovered.terrain, closedPolygon(boundary))), 0);
});
