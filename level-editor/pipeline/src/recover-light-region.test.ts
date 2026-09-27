import test from "node:test";
import assert from "node:assert/strict";
import {
  containsLightPolygon,
  recoverLightPlane,
  recoverLightRegion,
} from "./recover-light-region.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import type { LightSector, MotionArea, SightObstacle } from "../../shared/src/level.ts";

const light: LightSector = {
  layer: 0,
  ambience: 5,
  polygon: {
    points: [
      [10, 10],
      [30, 10],
      [30, 30],
      [10, 30],
    ],
  },
};
test("light ownership spans parts of one asset but rejects enclosed unowned gaps", () => {
  const rectangle = (x1: number, y1: number, x2: number, y2: number): [number, number][] => [
    [x1, y1],
    [x2, y1],
    [x2, y2],
    [x1, y2],
  ];
  assert.ok(
    containsLightPolygon(light.polygon.points, [
      rectangle(10, 10, 20, 30),
      rectangle(20, 10, 30, 30),
    ]),
  );
  assert.equal(
    containsLightPolygon(light.polygon.points, [
      rectangle(10, 10, 30, 15),
      rectangle(10, 25, 30, 30),
      rectangle(10, 15, 15, 25),
      rectangle(25, 15, 30, 25),
    ]),
    false,
  );
  assert.equal(containsLightPolygon(light.polygon.points, []), false);
});
test("ground light recovery localizes geometry and retains ambience without layer indices", () => {
  const plane = recoverLightPlane(light, []);
  assert.deepEqual(plane, [0, 0, 0]);
  const result = recoverLightRegion(light, "shadow", "wall", plane, ([x, y, z]) => [
    x - 10,
    y - 20,
    z,
  ]);
  assert.deepEqual(result, {
    id: "shadow",
    node: "wall",
    ambiences: 5,
    polygon: [
      [0, -10, 0],
      [20, -10, 0],
      [20, 10, 0],
      [0, 10, 0],
    ],
  });
});
test("light recovery uses projected elevation and refuses mixed or unsupported planes", () => {
  const { hut } = assetCompilerFixture();
  const support: SightObstacle = {
    ...hut.parts[0]!.obstacle_local_game!,
    projection_area: [0, 1],
    points: [
      [0, 0],
      [100, 0],
      [100, 100],
      [0, 100],
    ].map(([x, y]) => ({ x: x!, y: y! + 40, z_bottom: 0, z_top: 40 })),
  };
  const upper = { ...light, layer: 1 };
  assert.deepEqual(recoverLightPlane(upper, [support]), [0, 0, 40]);
  support.points[3]!.z_top += 0.01;
  support.points[3]!.y += 0.01;
  assert.deepEqual(recoverLightPlane(upper, [support]), [0, 0, 40]);
  assert.deepEqual(
    recoverLightRegion(upper, "light", "roof", [0, 0, 40], (p) => p).polygon[0],
    [10, 50, 40],
  );
  assert.throws(() => recoverLightPlane(upper, []), /uncovered elevated/);
  support.projection_area = [0, 0];
  support.points[1]!.x = support.points[2]!.x = 20;
  assert.throws(() => recoverLightPlane(light, [support]), /crosses receiving planes/);
});

for (const layer of [0, 1])
  test(`raised light contours on layer ${layer} can extend beyond navigation but not across receiving gaps`, () => {
    const { hut } = assetCompilerFixture();
    const support: SightObstacle = {
      ...hut.parts[0]!.obstacle_local_game!,
      projection_area: [0, layer],
      points: [
        [0, 0],
        [20, 0],
        [20, 100],
        [0, 100],
      ].map(([x, y]) => ({ x: x!, y: y! + 40, z_bottom: 0, z_top: 40 })),
    };
    const upper = { ...light, layer };
    const area: MotionArea = {
      is_lift: false,
      state_id: 0,
      flags: 0,
      skeleton_segments: [],
      obstacles: [],
      polygon: {
        points: [
          [0, 0],
          [20, 0],
          [20, 100],
          [0, 100],
        ],
      },
    };
    const plane = recoverLightPlane(upper, [support], [area]);
    assert.deepEqual(plane, [0, 0, 40]);
    assert.deepEqual(
      recoverLightRegion(upper, "shadow", "roof", plane, (point) => point).polygon,
      light.polygon.points.map(([x, y]) => [x, y + 40, 40]),
    );
    area.polygon.points[1]![0] = area.polygon.points[2]![0] = 40;
    assert.throws(
      () => recoverLightPlane(upper, [support], [area]),
      /uncovered elevated|crosses receiving/,
    );
    area.obstacles = [
      {
        state_id: 0,
        polygon: {
          points: [
            [20, 0],
            [40, 0],
            [40, 100],
            [20, 100],
          ],
        },
      },
    ];
    assert.deepEqual(recoverLightPlane(upper, [support], [area]), [0, 0, 40]);
    area.obstacles[0]!.state_id = 1;
    assert.throws(
      () => recoverLightPlane(upper, [support], [area]),
      /uncovered elevated|crosses receiving/,
    );
    if (layer === 0) assert.deepEqual(recoverLightPlane(upper, [], []), [0, 0, 0]);
    else assert.throws(() => recoverLightPlane(upper, [], []), /no receiving geometry/);
  });
