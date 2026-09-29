import test from "node:test";
import assert from "node:assert/strict";
import type { Polygon } from "polygon-clipping";
import { partitionMovementObstacles } from "./partition-movement-obstacles.ts";
import { fixedPolygonBoolean } from "./fixed-polygon-boolean.ts";

test("recovery partitions a nearly touching hole without filling it", () => {
  const region: Polygon = [
    [
      [206110849 / 1048576, 611038976 / 1048576],
      [194, 582],
      [177, 602],
      [158, 592],
      [185292163 / 1048576, 603101552 / 1048576],
      [206110849 / 1048576, 611038976 / 1048576],
    ],
    [
      [177250104 / 1048576, 610339406 / 1048576],
      [166651440 / 1048576, 619878203 / 1048576],
      [185455136 / 1048576, 628313974 / 1048576],
      [192443445 / 1048576, 623189231 / 1048576],
      [200043218 / 1048576, 614248321 / 1048576],
      [182594306 / 1048576, 606420337 / 1048576],
      [177250104 / 1048576, 610339406 / 1048576],
    ],
  ];
  assert.throws(() => partitionMovementObstacles(region), /changed coverage/);
  const pieces = partitionMovementObstacles(region, true);
  const delta = fixedPolygonBoolean(
    "xor",
    region,
    pieces.map((p) => [p]),
  );
  const area = delta.reduce(
    (sum, polygon) =>
      sum +
      polygon.reduce(
        (s, ring, i) =>
          s +
          ((i ? -1 : 1) *
            Math.abs(
              ring.reduce((a, p, j) => {
                const q = ring[(j + 1) % ring.length]!;
                return a + p[0] * q[1] - q[0] * p[1];
              }, 0),
            )) /
            2,
        0,
      ),
    0,
  );
  assert(area < 0.001, `Partition coverage error: ${area}`);
});
