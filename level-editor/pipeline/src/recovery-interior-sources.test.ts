import test from "node:test";
import assert from "node:assert/strict";
import {
  declaredInteriorSources,
  type InteriorSourceDeclaration,
} from "./recovery-interior-sources.ts";

function fixture(): InteriorSourceDeclaration {
  return {
    building: 5,
    reason: "Two entrances joined through a wall passage",
    pieces: [
      {
        owner: "west",
        node: "body",
        doors: [8],
        joins: [{ point: [0, 0, 20], direction: [1, 0] }],
      },
      {
        owner: "wall",
        node: "body",
        doors: [],
        joins: [
          { point: [0, 0, 20], direction: [-1, 0] },
          { point: [10, 0, 20], direction: [1, 0] },
        ],
      },
      {
        owner: "east",
        node: "body",
        doors: [9],
        joins: [{ point: [10, 0, 20], direction: [-1, 0] }],
      },
    ],
  };
}
const rooms = new Map([[5, [8, 9]]]);
const frames = (asset: string, node: string) => [{ asset, node }];

test("shared room recovery assigns each door once and retains a doorless connector", () => {
  const declaration = fixture();
  const result = declaredInteriorSources([declaration], rooms, frames).get(5)!;
  assert.equal(result.length, 3);
  assert.deepEqual(
    result.map((piece) => piece.doors),
    [[8], [], [9]],
  );
  assert.deepEqual(result[2]!.frame, { asset: "east", node: "body" });
  result[0]!.joins[0]!.point[0] = 99;
  assert.equal(declaration.pieces[0]!.joins[0]!.point[0], 0);
});

test("shared room recovery rejects missing, duplicated or unrelated entrances", () => {
  for (const doors of [[], [8], [10]]) {
    const declaration = fixture();
    declaration.pieces[2]!.doors = doors;
    assert.throws(
      () => declaredInteriorSources([declaration], rooms, frames),
      /every entrance exactly once/,
    );
  }
  assert.throws(() => declaredInteriorSources([fixture()], new Map(), frames), /one source room/);
  assert.throws(
    () => declaredInteriorSources([fixture(), fixture()], rooms, frames),
    /one source room/,
  );
});

test("shared room recovery rejects missing frames and disconnected or invalid sockets", () => {
  assert.throws(() => declaredInteriorSources([fixture()], rooms, () => []), /pinned frame/);
  assert.throws(() => declaredInteriorSources([fixture()], rooms, () => [1, 2]), /pinned frame/);
  const disconnected = fixture();
  disconnected.pieces[2]!.joins[0]!.point[0] += 1;
  assert.throws(() => declaredInteriorSources([disconnected], rooms, frames), /connect all pieces/);
  disconnected.pieces[2]!.joins[0]!.direction = [NaN, 0];
  assert.throws(
    () => declaredInteriorSources([disconnected], rooms, frames),
    /Invalid shared interior socket/,
  );
  const duplicate = fixture();
  duplicate.pieces[2]!.owner = "west";
  assert.throws(() => declaredInteriorSources([duplicate], rooms, frames), /distinct assets/);
});
