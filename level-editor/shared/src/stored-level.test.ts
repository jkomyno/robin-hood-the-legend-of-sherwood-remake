import test from "node:test";
import assert from "node:assert/strict";
import { parseStoredMap, serializeStoredMap } from "./stored-level.ts";
import { assetCompilerFixture } from "../test-fixtures/asset-gameplay.ts";

test("saving and reopening restores empty terrain resources when the descriptor omits them", () => {
  const { document, assets, hut } = assetCompilerFixture();
  const ground = { ...structuredClone(hut), id: "ground", parts: [], model: "model.glb" };
  delete ground.resources;
  assets.set(ground.id, ground);
  document.sceneAssets = [
    {
      id: "ground",
      role: "ground",
      model: "3d-assets/ground/model.glb",
      model_sha256: "a".repeat(64),
      descriptor: "3d-assets/ground/asset.json",
      descriptor_sha256: "b".repeat(64),
      resources: [],
    },
  ];
  const saved = serializeStoredMap(document, assets);
  const restored = parseStoredMap(saved, assets);
  assert.deepEqual(restored.sceneAssets[0]!.resources, []);
  assert.deepEqual(parseStoredMap(serializeStoredMap(restored, assets), assets), restored);
  document.sceneAssets[0]!.resources = [{ path: "unexpected.png", sha256: "c".repeat(64) }];
  assert.throws(() => parseStoredMap(document, assets), /resources differ/);
});
