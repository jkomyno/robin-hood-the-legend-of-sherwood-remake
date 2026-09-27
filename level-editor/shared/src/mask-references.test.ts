import test from "node:test";
import assert from "node:assert/strict";
import { maskReferenceResolver } from "./mask-references.ts";

test("mask references resolve each layer independently of global ordering", () => {
  const resolve = maskReferenceResolver([
    { layer: 2 },
    { layer: 0 },
    { layer: 2 },
    { layer: 7 },
    { layer: 0 },
  ]);
  assert.deepEqual(
    resolve([
      { layer: 0, index: 1 },
      { layer: 2, index: 0 },
      { layer: 7, index: 0 },
    ]),
    [4, 0, 3],
  );
  assert.deepEqual(resolve([]), []);
});

test("mask references reject flat indices, missing layers and invalid local indices", () => {
  const resolve = maskReferenceResolver([{ layer: 2 }]);
  for (const refs of [
    undefined,
    [0],
    [null],
    [{ layer: 0, index: 0 }],
    [{ layer: 2, index: 1 }],
    [{ layer: 2, index: -1 }],
    [{ layer: 2, index: 0.5 }],
    [{ layer: 65536, index: 0 }],
  ])
    assert.throws(() => resolve(refs, "old_masks"), /old_masks/);
  assert.throws(() => maskReferenceResolver([{ layer: NaN }]), /invalid layer/);
});
