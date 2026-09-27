import test from "node:test";
import assert from "node:assert/strict";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { diagnoseGameplayCandidates } from "./diagnose-gameplay-candidates.ts";

test("a passing geometry probe does not certify uncompiled state behaviour", () => {
  const { document, assets } = assetCompilerFixture();
  document.groups[0]!.states = {
    active: "initial",
    initial: [document.objects[0]!.id],
    applied: [],
  };
  const before = structuredClone(document);
  const result = diagnoseGameplayCandidates(document, assets);
  assert.equal(result.compilation.ready, false);
  assert.match(result.compilation.error!, /state transitions/);
  assert.equal(result.staticGeometry.ready, true);
  assert.equal(result.staticGeometry.scope, "current-visible-geometry-only");
  assert.deepEqual(document, before);
  delete assets.get("hut")!.gameplay;
  const missing = diagnoseGameplayCandidates(document, assets);
  assert.equal(missing.staticGeometry.ready, false);
  assert.match(missing.staticGeometry.error!, /Missing asset gameplay definitions/);
});
