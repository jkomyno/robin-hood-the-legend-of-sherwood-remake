import test from "node:test";
import assert from "node:assert/strict";
import { recoverLiftJoins } from "./recover-lift-joins.ts";
import type { Vec3 } from "@rle/shared";

test("compound lift recovery stores identical sockets across a fractional height seam", () => {
  const low: Vec3[] = [
    [0, 0, 0],
    [10, 0, 10],
    [10, 10, 10],
    [0, 10, 0],
  ];
  const high: Vec3[] = [
    [10, 0, 10.07],
    [20, 0, 15],
    [20, 10, 15],
    [10, 10, 10.07],
  ];
  assert.deepEqual(recoverLiftJoins([low, high]), [[[10, 5, 10.035]], [[10, 5, 10.035]]]);
  assert.throws(() => recoverLiftJoins([low, low]), /unambiguous shared edge/);
  assert.throws(
    () => recoverLiftJoins([low, high.map(([x, y, z]) => [x + 100, y, z])]),
    /without a shared edge/,
  );
});
