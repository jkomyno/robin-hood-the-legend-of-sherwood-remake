import test from "node:test";
import assert from "node:assert/strict";
import { appearanceOnlyCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { recoverAppearanceBindings } from "./recover-appearance-bindings.ts";

test("appearance recovery retains local ownership and deduplicates recovery evidence", () => {
  const { document, hut } = appearanceOnlyCompilerFixture();
  document.groups[0]!.patches = { hut: { roof: "patch-001" } };
  const definition = hut.gameplay!.movementTransitions!;
  delete definition[0]!.appearances;
  const evidence = { asset: "hut", patch: 1, transition: "barriers" };
  const result = recoverAppearanceBindings(
    document,
    2,
    [evidence, evidence],
    new Map([["hut", definition]]),
  );
  assert.deepEqual(result, { bindings: [{ ...evidence, appearance: "roof" }], unresolved: [] });
  assert.equal(definition[0]!.appearances, undefined);
  const foreign = recoverAppearanceBindings(
    document,
    2,
    [{ ...evidence, asset: "neighbor" }],
    new Map([["hut", definition]]),
  );
  assert.equal(foreign.bindings.length, 0);
  assert.match(foreign.unresolved[0]!.reason, /explicit join/);
});

test("appearance recovery refuses ambiguous placements, mission aliases and absent definitions", () => {
  const { document, hut } = appearanceOnlyCompilerFixture();
  const evidence = [{ asset: "hut", patch: 1, transition: "barriers" }];
  const definitions = new Map([["hut", hut.gameplay!.movementTransitions!]]);
  for (const alias of ["mission-1-patch-001", "preview", "patch-002", "patch-0001"]) {
    document.groups[0]!.patches = { hut: { roof: alias } };
    const result = recoverAppearanceBindings(document, 2, evidence, definitions);
    assert.equal(result.bindings.length, 0);
    assert.equal(result.unresolved.length, 1);
  }
  document.groups[0]!.patches = { hut: { roof: "patch-001" } };
  assert.match(
    recoverAppearanceBindings(document, 2, evidence, new Map()).unresolved[0]!.reason,
    /definition/,
  );
  document.objects[0]!.patches = { hut: { roof: "patch-000" } };
  assert.match(
    recoverAppearanceBindings(document, 2, evidence, definitions).unresolved[0]!.reason,
    /Conflicting/,
  );
});
