import test from "node:test";
import assert from "node:assert/strict";
import { assembleJumpSegments, type PlacedJumpSegment } from "./assemble-jump-segments.ts";

test("jump socket matching rejects ambiguity and conflicting traversal rules", () => {
  const a: PlacedJumpSegment = {
    id: "a",
    long: true,
    join: [50, 50, 50],
    edge: { zone: "low", a: [0, 0, 0], b: [0, 10, 0] },
  };
  const b: PlacedJumpSegment = {
    ...a,
    id: "b",
    edge: { zone: "high", a: [100, 0, 100], b: [100, 10, 100] },
  };
  assert.equal(assembleJumpSegments([a, b]).pairs.length, 1);
  assert.deepEqual(assembleJumpSegments([a]), { pairs: [], unmatched: [a] });
  assert.throws(() => assembleJumpSegments([a, b, { ...b, id: "c" }]), /exactly one complementary/);
  assert.throws(() => assembleJumpSegments([a, { ...b, long: false }]), /rules disagree/);
  assert.throws(() => assembleJumpSegments([a, { ...b, edge: a.edge }]), /same landing zone/);
});
