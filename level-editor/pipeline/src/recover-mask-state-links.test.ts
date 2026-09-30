import test from "node:test";
import assert from "node:assert/strict";
import { maskAssetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { recoverMaskStateLinks } from "./recover-mask-state-links.ts";

test("recovered mask state links compile to fresh indices for each placed asset", () => {
  const { document, assets, hut } = maskAssetCompilerFixture();
  const bounds: [number, number, number, number] = [0, 0, 2000, 2000];
  const originals = compileAssetGameplay(document, assets, bounds).masks!;
  const masks = [
    { ...originals[0]!, layer: 1 },
    { ...originals[1]!, layer: 0 },
    { ...originals[0]!, layer: 0 },
  ];
  const ids = hut.gameplay!.masks!.map((m) => m.id);
  const owners = new Map([
    [2, { asset: hut.id, id: ids[0]! }],
    [1, { asset: hut.id, id: ids[1]! }],
  ]);
  const links = recoverMaskStateLinks(
    masks,
    { old_masks: [{ layer: 0, index: 1 }], new_masks: [{ layer: 0, index: 0 }] },
    hut.id,
    owners,
  );
  assert.deepEqual(links, { initialMasks: [ids[0]], appliedMasks: [ids[1]] });
  Object.assign(hut.gameplay!.movementTransitions![0]!, links);
  const part = document.objects.find((p) => p.group)!;
  document.groups.push({ id: "copy", transform: { dx: 1000, dy: 0, dz: 0, rot_deg: 0 } });
  document.objects.push({ ...structuredClone(part), id: "copy-part", group: "copy" });
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    compiled.movement_transitions!.map((t) => [t.initial_masks, t.applied_masks]),
    [
      [[0], [1]],
      [[2], [3]],
    ],
  );
});

test("mask state recovery cannot silently omit masks or cross asset ownership", () => {
  const { document, assets } = maskAssetCompilerFixture();
  const masks = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]).masks!;
  const patch = { old_masks: [{ layer: 0, index: 0 }], new_masks: [{ layer: 0, index: 1 }] };
  assert.throws(() => recoverMaskStateLinks(masks, patch, "a", new Map()), /no recovered/);
  assert.throws(
    () => recoverMaskStateLinks(masks, patch, "a", new Map([[0, { asset: "b", id: "mask" }]])),
    /another asset/,
  );
  assert.throws(
    () =>
      recoverMaskStateLinks(
        masks,
        patch,
        "a",
        new Map([
          [0, { asset: "a", id: "mask" }],
          [1, { asset: "a", id: "mask" }],
        ]),
      ),
    /reuses/,
  );
});
