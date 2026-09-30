import test from "node:test";
import assert from "node:assert/strict";
import { maskAssetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { reviewedMaskStateBindings } from "./reviewed-mask-state-bindings.ts";

test("reviewed masks require complete, unique local transition ownership", () => {
  const { document, assets } = maskAssetCompilerFixture();
  const masks = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]).masks!;
  const patches = [{ old_masks: [{ layer: 0, index: 0 }], new_masks: [{ layer: 0, index: 1 }] }];
  const recipes = [
    {
      asset: "hut",
      entries: [
        { source: 0, id: "covered" },
        { source: 1, id: "revealed" },
      ],
    },
  ];
  const transitions = [{ patch: 0, asset: "hut", transition: "cover-state" }];
  const bindings = reviewedMaskStateBindings(masks, patches, recipes, transitions);
  assert.deepEqual(
    [...bindings],
    [
      [0, { asset: "hut", transition: "cover-state", phase: "initial" }],
      [1, { asset: "hut", transition: "cover-state", phase: "applied" }],
    ],
  );
  assert.deepEqual(
    reviewedMaskStateBindings(masks, patches, recipes, [...transitions, ...transitions]),
    bindings,
  );
  assert.equal(reviewedMaskStateBindings(masks, [], recipes, []).size, 0);
  assert.throws(
    () => reviewedMaskStateBindings(masks, patches, recipes, []),
    /requires state recovery/,
  );
  assert.throws(
    () =>
      reviewedMaskStateBindings(
        masks,
        patches,
        [{ ...recipes[0]!, entries: recipes[0]!.entries.slice(0, 1) }],
        transitions,
      ),
    /no recovered/,
  );
  assert.throws(
    () =>
      reviewedMaskStateBindings(masks, patches, [{ ...recipes[0]!, asset: "other" }], transitions),
    /another asset/,
  );
  assert.throws(
    () => reviewedMaskStateBindings(masks, patches, [...recipes, ...recipes], transitions),
    /duplicate/,
  );
  assert.throws(
    () =>
      reviewedMaskStateBindings(masks, patches, recipes, [
        ...transitions,
        { ...transitions[0]!, transition: "other" },
      ]),
    /requires state recovery/,
  );
  assert.throws(
    () =>
      reviewedMaskStateBindings(masks, [...patches, ...patches], recipes, [
        ...transitions,
        { ...transitions[0]!, patch: 1 },
      ]),
    /multiple state controllers/,
  );
});
