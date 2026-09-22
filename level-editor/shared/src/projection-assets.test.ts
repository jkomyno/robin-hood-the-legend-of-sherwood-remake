import test from "node:test";
import assert from "node:assert/strict";
import { parseExternalAssetSources, parseProjectionAssetDescriptor, parseProjectionAssetIndex, parseLevel3D } from "./validation.ts";
import { assetNodeKey, safeLibraryPath } from "./projection-assets.ts";

const obstacle = { points: [{ x: 0, y: 0, z_bottom: 0, z_top: 10 }, { x: 10, y: 0, z_bottom: 0, z_top: 10 }, { x: 0, y: 10, z_bottom: 0, z_top: 10 }],
  opaque: true, solid: true, mouse: true, show_shadow_polygon: true, default_material: 0, material_indices: [], projection_area: null };
const descriptor = { version: 1, kind: "projection-mapped-asset", id: "house", name: "House", source_map: "Leicester", model: "model.glb",
  source_origin_scene: [20, -40, 0], source_origin_game: [20, 23, 0], parts: [{ node: "building-000", name: "Wall", source_obstacle: 0, obstacle_local_game: obstacle, default_hidden: true }] };
const reference = { id: "house", descriptor: "3d-assets/house/asset.json", model: "3d-assets/house/model.glb", descriptor_sha256: "a".repeat(64), model_sha256: "b".repeat(64) };

test("projection descriptors retain extras and state defaults while validating local parts", () => {
  const value = { ...descriptor, reveal: { source: "evidence" } };
  assert.equal(parseProjectionAssetDescriptor(value), value);
  assert.throws(() => parseProjectionAssetDescriptor({ ...descriptor, parts: [...descriptor.parts, ...descriptor.parts] }), /duplicate/);
  assert.throws(() => parseProjectionAssetDescriptor({ ...descriptor, parts: [{ ...descriptor.parts[0], source_obstacle: 1 }] }), /canonical/);
  assert.throws(() => parseProjectionAssetDescriptor({ ...descriptor, parts: [{ ...descriptor.parts[0], default_hidden: "yes" }] }), /default_hidden/);
  assert.throws(() => parseProjectionAssetDescriptor({ ...descriptor, model: "../model.glb" }), /safe/);
});

test("library paths and identities reject traversal and duplicate source records", () => {
  for (const path of ["../a", "/a", "a//b", "a/./b", "C:/a", "a\\b", "a?x", "a%2fb", "a#x"])
    assert.equal(safeLibraryPath(path), false, path);
  assert.equal(safeLibraryPath("3d-assets/house/model.glb"), true);
  assert.equal(parseExternalAssetSources([reference])[0], reference);
  assert.throws(() => parseExternalAssetSources([reference, reference]), /duplicate/);
  assert.throws(() => parseExternalAssetSources([{ ...reference, model_sha256: "bad" }]), /SHA-256/);
  assert.throws(() => parseProjectionAssetIndex({ version: 1, assets: [{ id: "house", name: "House", source_map: "Leicester", descriptor: "../asset.json", model: "model.glb" }] }), /safe/);
});

test("documents preserve pinned external sources and reject dangling namespaces", () => {
  const document = { version: 1, map: "Leicester", glb: "map.glb", size: [100, 100], camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    groups: [], assetSources: [reference], objects: [{ id: "copy", node: assetNodeKey("house", "building-000"), kind: "building", source: { map: "Leicester", obstacle: 0 },
      obstacle, transform: { dx: 0, dy: 0, dz: 0, rot_deg: 0 } }] };
  assert.equal(parseLevel3D(document).assetSources?.[0], reference);
  assert.throws(() => parseLevel3D({ ...document, assetSources: [] }), /dangling external/);
  assert.equal(parseLevel3D({ ...document, assetSources: undefined, objects: [] }).assetSources, undefined);
});
