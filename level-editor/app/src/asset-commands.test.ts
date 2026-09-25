import test from "node:test";
import assert from "node:assert/strict";
import { IDENTITY_TRANSFORM, type Level3D, type ProjectionAssetDescriptor, type ExternalAssetSource } from "@rle/shared";
import { insertProjectionAsset } from "./asset-commands.ts";
import { duplicateSelection, deleteSelection, patchGroup } from "./document-commands.ts";

export function assetFixture() {
  const obstacle = { points: [{ x: 0, y: 0, z_bottom: 0, z_top: 10 }, { x: 10, y: 0, z_bottom: 0, z_top: 10 }, { x: 0, y: 10, z_bottom: 0, z_top: 10 }],
    opaque: true, solid: true, mouse: true, show_shadow_polygon: true, default_material: 0, material_indices: [], projection_area: null };
  const descriptor: ProjectionAssetDescriptor = { version: 1, kind: "projection-mapped-asset", id: "house", name: "House", source_map: "Leicester", model: "model.glb",
    source_origin_scene: [20, -40, 0], source_origin_game: [20, 23, 0], parts: [0, 1].map(n => ({ node: `building-00${n}`, name: n ? "Roof" : "Wall", source_obstacle: n, obstacle_local_game: structuredClone(obstacle), default_hidden: n === 1 })) };
  const reference: ExternalAssetSource = { id: "house", descriptor: "3d-assets/house/asset.json", model: "3d-assets/house/model.glb", descriptor_sha256: "a".repeat(64), model_sha256: "b".repeat(64) };
  const document: Level3D = { version: 1, map: "Leicester", glb: "map.glb", size: [100, 100], camera: { kind: "oblique-orthographic", elevation_deg: 35 }, groups: [], objects: [] };
  return { descriptor, reference, document };
}

test("standalone insertion creates a complete independent group and preserves default visibility", () => {
  const { descriptor, reference, document } = assetFixture();
  const before = structuredClone(document);
  const one = insertProjectionAsset(document, descriptor, reference, [50, 40, 0]);
  const two = insertProjectionAsset(one.document, descriptor, reference, [80, 20, 3]);
  assert.deepEqual(document, before);
  assert.equal(two.document.assetSources?.length, 1);
  assert.equal(two.document.groups.length, 2);
  assert.equal(new Set(two.document.objects.map(part => part.id)).size, 4);
  assert.equal(two.document.objects[1]!.hidden, true);
  assert.equal(two.document.objects[0]!.node, "asset:house:building-000");
  assert.deepEqual(two.document.groups[0]!.transform, { dx: 50, dy: 40, dz: 0, rot_deg: 0 });
  two.document.objects[2]!.obstacle.points[0]!.x = 99;
  assert.equal(two.document.objects[0]!.obstacle.points[0]!.x, 0);
  assert.equal(descriptor.parts[0]!.obstacle_local_game.points[0]!.x, 0);
  const moved = patchGroup(one.document, one.selection.id, { transform: { ...IDENTITY_TRANSFORM, dx: 7 } });
  assert.equal(one.document.groups[0]!.transform.dx, 50);
  const duplicate = duplicateSelection(moved, one.selection);
  assert.equal(duplicate.document.objects.length, 4);
  assert.equal(deleteSelection(duplicate.document, duplicate.selection).objects.length, 2);
});

test("changed revisions and invalid placements fail without edits", () => {
  const { descriptor, reference, document } = assetFixture();

  const inserted = insertProjectionAsset(document, descriptor, reference, [0, 0, 0]);
  assert.throws(() => insertProjectionAsset(inserted.document, descriptor, { ...reference, model_sha256: "c".repeat(64) }, [0, 0, 0]), /different revision/);
  assert.throws(() => insertProjectionAsset(document, descriptor, reference, [NaN, 0, 0]), /placement/);
  assert.equal(document.groups.length, 0);
});

test("map backgrounds cannot be inserted as editable instances", () => {
  const { descriptor, reference, document } = assetFixture();
  const ground = { ...descriptor, editor_usage: "map-background" as const, parts: [], components: [{ source_node: "ground" }] };
  assert.throws(() => insertProjectionAsset(document, ground, reference, [0, 0, 0]), /cannot be inserted/);
  assert.equal(document.groups.length, 0);
});

test("shared assets keep source provenance when placed in a different level", () => {
  const { descriptor, reference, document } = assetFixture();
  const result = insertProjectionAsset({ ...document, map: "York" }, descriptor, reference, [12, 34, 5]);
  assert.equal(result.document.map, "York");
  assert.equal(result.document.objects[0]!.source.map, "Leicester");
  assert.equal(result.document.groups[0]!.transform.dx, 12);
});

test("inserting a split part retains its scoped footprint and source provenance", () => {
  const {descriptor,reference,document}=assetFixture();
  descriptor.parts=[{...descriptor.parts[0]!,node:"building-000--component-west",source_obstacle:0,source_components:["west"]}];
  const result=insertProjectionAsset(document,descriptor,reference,[10,20,0]);
  assert.deepEqual(result.document.objects[0]!.source,{map:"Leicester",obstacle:0,components:["west"]});
  assert.deepEqual(result.document.objects[0]!.obstacle,descriptor.parts[0]!.obstacle_local_game);
  assert.equal(result.document.objects[0]!.node,"asset:house:building-000--component-west");
});
