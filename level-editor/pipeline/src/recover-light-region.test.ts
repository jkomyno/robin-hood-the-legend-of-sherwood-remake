import test from "node:test";
import assert from "node:assert/strict";
import { recoverLightPlane, recoverLightRegion } from "./recover-light-region.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import type { LightSector, SightObstacle } from "../../shared/src/level.ts";

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
  assert.deepEqual(
    recoverLightRegion(upper, "light", "roof", [0, 0, 40], (p) => p).polygon[0],
    [10, 50, 40],
  );
  assert.throws(() => recoverLightPlane(upper, []), /uncovered elevated/);
  support.projection_area = [0, 0];
  support.points[1]!.x = support.points[2]!.x = 20;
  assert.throws(() => recoverLightPlane(light, [support]), /crosses receiving planes/);
});
