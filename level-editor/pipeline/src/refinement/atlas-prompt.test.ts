import assert from "node:assert/strict";
import test from "node:test";
import { atlasPrompt } from "./atlas-prompt.ts";

test("UV atlas preserves nonplanar terrain and requires aligned lighting", () => {
  const prompt = atlasPrompt("uv-atlas", 1, "short", true)!;
  assert.match(prompt, /modeled height changes/);
  assert.match(prompt, /same UV coordinates/);
  assert.doesNotMatch(prompt, /eight views|planar surface/);
  assert.throws(() => atlasPrompt("uv-atlas", 1, "short", false), /lighting reference/);
});
test("atlas layouts cannot accidentally use eight-view or gatehouse prompts", () => {
  for (const kind of ["planar-atlas", "uv-atlas"]) {
    assert.throws(() => atlasPrompt(kind, 8, "short", true), /exactly one view/);
    assert.throws(() => atlasPrompt(kind, 1, "detailed", true), /short prompt/);
  }
  assert.equal(atlasPrompt(undefined, 8, "short", true), undefined);
  assert.match(atlasPrompt("planar-atlas", 1, "short", true)!, /without inventing terrain relief/);
});
