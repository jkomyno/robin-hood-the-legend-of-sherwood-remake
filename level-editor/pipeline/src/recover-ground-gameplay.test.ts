import test from "node:test";
import assert from "node:assert/strict";
import clipping, { type MultiPolygon } from "polygon-clipping";
import { closedPolygon, polygonArea, recoverGroundGameplay } from "./recover-ground-gameplay.ts";
import type { Point } from "@rle/shared";

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
