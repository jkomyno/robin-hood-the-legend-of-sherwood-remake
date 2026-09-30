import test from "node:test";
import assert from "node:assert/strict";
import { assembleTransitions, type PlacedTransitionJoin } from "./assemble-transitions.ts";
import type { CompiledAssetGeometry } from "./asset-gameplay.ts";

type Transition = NonNullable<CompiledAssetGeometry["movement_transitions"]>[number];
const transition = (id: string): Transition => ({
  id,
  waypoint: [1, 1],
  sector: 0,
  layer: 0,
  active: true,
  definitive: false,
  apply_polygon: { points: [] },
  no_apply_polygon: { points: [] },
  motion_changes: [],
  has_appearance: true,
});
const joins = (points: number[]) =>
  new Map<string, PlacedTransitionJoin>(
    points.map((x, i) => [String(i), { key: "roof", point: [x, 0, 0] }]),
  );

test("transition contacts merge all effect bindings without mutating members", () => {
  const a = transition("0"),
    b = transition("1");
  a.initial_masks = [0];
  b.initial_masks = [1];
  a.applied_masks = [2];
  b.applied_masks = [3];
  a.door_links = { mode: "swap-rights", indices: [0] };
  b.door_links = { mode: "swap-rights", indices: [1] };
  const before = structuredClone([a, b]);
  const merged = assembleTransitions([b, a], joins([0, 0]));
  assert.equal(merged.length, 1);
  assert.equal(merged[0]!.id, "0");
  assert.deepEqual(merged[0]!.initial_masks, [0, 1]);
  assert.deepEqual(merged[0]!.applied_masks, [2, 3]);
  assert.deepEqual(merged[0]!.door_links, { mode: "swap-rights", indices: [0, 1] });
  assert.deepEqual([a, b], before);
  b.door_links.mode = "trigger-transition";
  assert.throws(() => assembleTransitions([a, b], joins([0, 0])), /conflicting door modes/);
  b.door_links.mode = "swap-rights";
  b.applied_masks = [0];
  assert.throws(() => assembleTransitions([a, b], joins([0, 0])), /conflicting state bindings/);
});

test("transition contacts require matching keys and reject ambiguous tolerance chains", () => {
  const parts = [transition("0"), transition("1"), transition("2")];
  assert.throws(
    () => assembleTransitions(parts, joins([0, 0.009, 0.018])),
    /Ambiguous transition join/,
  );
  assert.equal(assembleTransitions(parts, joins([0, 1, 2])).length, 3);
  const contacts = joins([0, 0, 0]);
  contacts.get("1")!.key = "another-roof";
  assert.equal(assembleTransitions(parts, contacts).length, 2);
});
