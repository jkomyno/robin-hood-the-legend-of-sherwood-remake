import test from "node:test";
import assert from "node:assert/strict";
import { recoverEndpointElevation, distanceToPolygon } from "./recovery-elevation.ts";

test("endpoint recovery uses the containing projection, not the first surface in a sector", () => {
  const distance = distanceToPolygon(
    [5, 5],
    [
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
    ],
  );
  assert.equal(distance, 0);
  assert.equal(
    recoverEndpointElevation(
      [
        { distance: 20, height: 3 },
        { distance, height: 100 },
      ],
      false,
    ),
    100,
  );
  assert.throws(
    () =>
      recoverEndpointElevation(
        [
          { distance: 0, height: 3 },
          { distance: 0, height: 100 },
        ],
        false,
      ),
    /Ambiguous/,
  );
  assert.throws(
    () =>
      recoverEndpointElevation(
        [
          { distance: 20, height: 3 },
          { distance: 30, height: 100 },
        ],
        false,
      ),
    /Ambiguous/,
  );
  assert.equal(
    recoverEndpointElevation(
      [
        { distance: 20, height: 100 },
        { distance: 30, height: 100 },
      ],
      false,
    ),
    100,
  );
  assert.equal(recoverEndpointElevation([], true), 0);
  assert.throws(() => recoverEndpointElevation([], false), /No projection/);
});
