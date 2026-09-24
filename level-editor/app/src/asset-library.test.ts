import test from "node:test";
import assert from "node:assert/strict";
import { assetTags, assetType, filterAssets } from "./asset-library.ts";

const entries = [
  { id: "house", name: "Town House", source_map: "York", descriptor: "house.json", model: "house.glb", tags: ["stone"] },
  { id: "tree", name: "Oak Tree", source_map: "Derby", descriptor: "tree.json", model: "tree.glb", asset_type: "Vegetation" },
  { id: "tower", name: "Tower", source_map: "Derby", descriptor: "tower.json", model: "tower.glb", asset_type: "Building" },
];
test("type, source and multiword search combine over the shared library", () => {
  assert.equal(filterAssets(entries, "", "", "").length, 3);
  assert.deepEqual(filterAssets(entries, "", "Building", "Derby").map(entry => entry.id), ["tower"]);
  assert.deepEqual(filterAssets(entries, "stone york", "Building", "").map(entry => entry.id), ["house"]);
  assert.equal(filterAssets(entries, "oak", "Building", "").length, 0);
  assert.equal(assetType({ ...entries[0]!, asset_type: "Prop" }), "Prop");
  assert.deepEqual(assetTags(entries[0]!), ["Building", "York", "stone"]);
});
