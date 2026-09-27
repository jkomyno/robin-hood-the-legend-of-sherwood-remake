import test from "node:test";
import assert from "node:assert/strict";
import { assembleInteriors, type PlacedInterior } from "./assemble-interiors.ts";

test("interior sockets require coincident positions and opposing directions", () => {
  const a: PlacedInterior = { id: "a", joins: [{ point: [1, 2, 3], direction: [1, 0] }] };
  const b: PlacedInterior = { id: "b", joins: [{ point: [1, 2, 3], direction: [-2, 0] }] };
  assert.deepEqual([...assembleInteriors([a, b]).values()], ["a", "a"]);
  b.joins[0]!.point[2] += 1;
  assert.deepEqual([...assembleInteriors([a, b]).values()], ["a", "b"]);
  b.joins[0]!.point[2] -= 1;
  b.joins[0]!.direction = [1, 0];
  assert.deepEqual([...assembleInteriors([a, b]).values()], ["a", "b"]);
  b.joins[0]!.direction = [0, 1];
  assert.deepEqual([...assembleInteriors([a, b]).values()], ["a", "b"]);
  b.joins[0]!.direction = [-1, 0];
  assert.throws(() => assembleInteriors([a, b, { ...b, id: "c" }]), /ambiguous/);
  assert.throws(
    () => assembleInteriors([{ id: "a", joins: [...a.joins, ...b.joins] }]),
    /ambiguous/,
  );
});
