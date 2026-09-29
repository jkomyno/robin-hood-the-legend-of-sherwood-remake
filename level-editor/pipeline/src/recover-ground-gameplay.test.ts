import test from "node:test";
import assert from "node:assert/strict";
import clipping, { type MultiPolygon } from "polygon-clipping";
import { closedPolygon, polygonArea, recoverGroundGameplay } from "./recover-ground-gameplay.ts";
import type { Point } from "@rle/shared";
import { preserveMovementBoundary } from "../../shared/src/preserve-movement-boundary.ts";
import { partitionMovementObstacles } from "../../shared/src/partition-movement-obstacles.ts";

test("boundary recovery retains explicit empty movement ownership", () => {
  const points: Point[] = [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100],
  ];
  const result = recoverGroundGameplay(
    [{ polygon: { points }, obstacles: [] }],
    [
      {
        asset: "stairs",
        node: "body",
        footprint: [
          [20, 20],
          [40, 20],
          [40, 40],
          [20, 40],
        ],
      },
      {
        asset: "unrelated",
        node: "body",
        footprint: [
          [200, 200],
          [240, 200],
          [240, 240],
          [200, 240],
        ],
      },
    ],
    true,
  );
  assert.deepEqual(result.blockers, [{ asset: "stairs", node: "body", regions: [], contours: [] }]);
  assert.equal(result.differenceArea, 0);
});

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

test("overlapping ownership cuts retain exact contour edges through extraction and compilation", () => {
  const boundary: Point[] = [
    [1200, 250],
    [1600, 250],
    [1600, 400],
    [1200, 400],
  ];
  const obstacle: Point[] = [
    [1268, 350],
    [1260, 342],
    [1350, 315],
    [1451, 298],
    [1511, 325],
    [1492, 359],
    [1452, 346],
    [1346, 366],
    [1324, 356],
    [1315, 338],
  ];
  assert.throws(
    () =>
      recoverGroundGameplay([{ polygon: { points: boundary }, obstacles: [] }], [], false, true),
    /require preserved movement boundaries/,
  );
  const footprints: Point[][] = [
    [
      [1346.1488, 365.8396],
      [1324.3048, 355.68484],
      [1345.7267, 340.52466],
      [1367.5707, 350.6794],
    ],
    [
      [1466.0311, 290.62598],
      [1470.933, 296.9099],
      [1267.0817, 349.224],
      [1262.1798, 342.94006],
    ],
    [
      [1346.117, 287.11295],
      [1368.1544, 316.1233],
      [1291.001, 335.405],
      [1268.9635, 306.39465],
    ],
    [
      [1268.964, 306.3947],
      [1291.0013, 335.40506],
      [1265.4781, 341.78363],
      [1243.4408, 312.7733],
    ],
    [
      [1454.2942, 336.14197],
      [1452.02, 352.75903],
      [1430.5603, 351.79285],
      [1432.8345, 335.17578],
    ],
  ];
  const recovered = recoverGroundGameplay(
    [{ polygon: { points: boundary }, obstacles: [{ polygon: { points: obstacle } }] }],
    footprints.map((footprint, index) => ({ asset: `wall-${index}`, node: "body", footprint })),
    true,
    true,
  );
  const section = recovered.sections[0]!;
  const fragments = [
    ...section.movementContours.flatMap((contour) =>
      contour.regions.flatMap((region) =>
        partitionMovementObstacles(region, true).map((points) => ({
          id: contour.id,
          polygon: [points],
        })),
      ),
    ),
    ...recovered.blockers.flatMap((blocker) =>
      blocker.contours!.flatMap((contour) =>
        contour.regions.map((polygon) => ({ id: contour.id, polygon })),
      ),
    ),
  ];
  const assembled = preserveMovementBoundary(
    boundary,
    fragments.map((fragment) => fragment.polygon),
    [],
    fragments.map((fragment) => fragment.id),
  );
  assert.deepEqual(
    clipping.xor(
      [obstacle],
      assembled.blockers.map((points) => [points]),
    ),
    [],
  );
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
