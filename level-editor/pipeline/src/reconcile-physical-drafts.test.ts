import test from "node:test";
import assert from "node:assert/strict";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { mergeGameplayDraft } from "./publish-gameplay-drafts.ts";
import {
  reconcilePhysicalDraft,
  verifyPhysicalModelFrames,
  verifyPhysicalPartIdentity,
} from "./reconcile-physical-drafts.ts";

test("reviewed physical reconciliation keeps artwork while default publication rejects changed volumes", () => {
  const { hut } = assetCompilerFixture();
  const live = structuredClone(hut),
    draft = structuredClone(hut);
  delete live.gameplay;
  live.model = "refined.glb";
  live.resources = [{ path: "textures/refined.png", sha256: "a".repeat(64) }];
  draft.parts[0]!.collision = "none";
  assert.throws(() => mergeGameplayDraft(live, draft, []), /frames differ/);
  const merged = reconcilePhysicalDraft(live, draft, ["Masks pending"]);
  assert.equal(merged.parts[0]!.collision, "none");
  assert.equal(merged.model, live.model);
  assert.deepEqual(merged.resources, live.resources);
  assert.ok(merged.gameplay?.draft?.issues.includes("Masks pending"));
  draft.parts[0]!.name = "Different part";
  assert.throws(() => reconcilePhysicalDraft(live, draft, []), /identity or frame/);
  assert.throws(
    () =>
      verifyPhysicalPartIdentity(
        [{ node: "a", author: "current" }],
        [{ node: "a", author: "stale" }],
      ),
    /authoring metadata/,
  );
});

test("model frame proof checks hierarchy, source identity and transforms independently of artwork", () => {
  const { hut } = assetCompilerFixture();
  const model = (offset = 0, sourceOffset = 0) => {
    const nodes = hut.parts.map((p) => ({
      name: p.node,
      translation: [offset, 0, 0],
      extras: { source_obstacle: (p.source_obstacle ?? 0) + sourceOffset },
    }));
    const json = Buffer.from(
      JSON.stringify({
        asset: { version: "2.0" },
        scenes: [{ nodes: nodes.map((_, i) => i) }],
        nodes,
      }),
    );
    const bytes = Buffer.alloc(20 + json.length);
    bytes.writeUInt32LE(0x46546c67, 0);
    bytes.writeUInt32LE(2, 4);
    bytes.writeUInt32LE(bytes.length, 8);
    bytes.writeUInt32LE(json.length, 12);
    bytes.writeUInt32LE(0x4e4f534a, 16);
    json.copy(bytes, 20);
    return bytes;
  };
  assert.equal(verifyPhysicalModelFrames(model(), hut, model(), hut), hut.parts.length);
  assert.throws(
    () => verifyPhysicalModelFrames(model(), hut, model(2), hut),
    /frames or source metadata differ/,
  );
  assert.throws(
    () => verifyPhysicalModelFrames(model(), hut, model(0, 1), hut),
    /source obstacle mismatch/,
  );
});
