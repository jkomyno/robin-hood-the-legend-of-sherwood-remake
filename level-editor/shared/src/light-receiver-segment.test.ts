import test from "node:test";
import assert from "node:assert/strict";
import { lightReceiverIntersection } from "./light-receiver-segment.ts";

test("finite light receiving segments follow slopes and reject out-of-range planes", () => {
  assert.deepEqual(
    lightReceiverIntersection(
      [
        [10, 20, 0],
        [10, 40, 20],
      ],
      [0.5, 0, 0],
    ),
    [10, 25, 5],
  );
  assert.deepEqual(
    lightReceiverIntersection(
      [
        [12, 20, 0],
        [12, 40, 20],
      ],
      [0.5, 0, 0],
    ),
    [12, 26, 6],
  );
  assert.equal(
    lightReceiverIntersection(
      [
        [10, 20, 0],
        [10, 40, 20],
      ],
      [0, 0, 30],
    ),
    undefined,
  );
  assert.throws(
    () =>
      lightReceiverIntersection(
        [
          [10, 25, 5],
          [20, 25, 5],
        ],
        [0, 0, 5],
      ),
    /lies in/,
  );
});
