import test from "node:test";
import assert from "node:assert/strict";
import {
  recoverSoundSource,
  containsSoundPolyline,
  uniqueSoundOwner,
} from "./recover-sound-source.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { soundAssetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";

test("overlapping parts share sound ownership only within the same asset", () => {
  const first = { asset: "tower", node: "building-001", frame: [10, 20] };
  const second = { asset: "tower", node: "building-002", frame: [30, 40] };
  assert.equal(uniqueSoundOwner([second, first]), first);
  assert.equal(uniqueSoundOwner([first, second]), first);
  assert.equal(uniqueSoundOwner([first]), first);
  assert.equal(uniqueSoundOwner([]), undefined);
  assert.equal(uniqueSoundOwner([first, second, { ...first, asset: "terrain" }]), undefined);
});

test("sound ownership checks segment interiors, not just vertices inside a concave part", () => {
  const boundary: [number, number][] = [
    [0, 0],
    [10, 0],
    [10, 10],
    [7, 10],
    [7, 3],
    [3, 3],
    [3, 10],
    [0, 10],
  ];
  assert.equal(
    containsSoundPolyline(
      [
        [1, 8],
        [9, 8],
      ],
      boundary,
    ),
    false,
  );
  assert.equal(
    containsSoundPolyline(
      [
        [1, 8],
        [1, 1],
        [9, 1],
        [9, 8],
      ],
      boundary,
    ),
    true,
  );
  assert.equal(
    containsSoundPolyline(
      [
        [3, 4],
        [3, 9],
      ],
      boundary,
    ),
    true,
  );
  assert.equal(containsSoundPolyline([[12, 0]], boundary), false);
});

test("one-time sound recovery reconstructs all source semantics after local placement", () => {
  const { document, assets, hut } = soundAssetCompilerFixture();
  const expected = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]).sound_sources!;
  hut.gameplay!.sounds = expected.map((raw, i) =>
    recoverSoundSource(raw, `sound-${i}`, "building-999", ([x, y, z]) => [x - 300, y - 300, z]),
  );
  assert.deepEqual(
    compileAssetGameplay(document, assets, [0, 0, 2000, 2000]).sound_sources,
    expected,
  );
  const bad = structuredClone(expected[0]!);
  bad.inner_volume = null;
  assert.throws(
    () => recoverSoundSource(bad, "bad", "building-999", (p) => p),
    /incomplete spatial data/,
  );
});
