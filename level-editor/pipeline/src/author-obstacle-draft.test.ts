import test from "node:test";
import assert from "node:assert/strict";
import { NodeIO } from "@gltf-transform/core";
import { authorObstacleDraft } from "./author-obstacle-draft.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import type { SightObstacle } from "../../shared/src/level.ts";

const shape: SightObstacle = {
  projection_area: null,
  points: [
    { x: 600, y: 600, z_bottom: 30, z_top: 32 },
    { x: 640, y: 600, z_bottom: 32, z_top: 34 },
    { x: 640, y: 620, z_bottom: 32, z_top: 34 },
    { x: 600, y: 620, z_bottom: 30, z_top: 32 },
  ],
  solid: true,
  opaque: true,
  mouse: true,
  show_shadow_polygon: true,
  default_material: 0,
  material_indices: [],
};
const options = {
  id: "camp-canopy",
  name: "Camp canopy",
  map: "test",
  sourceIndex: 35,
  origin: [620, 610, 0] as [number, number, number],
  camera: { kind: "oblique-orthographic" as const, elevation_deg: 35 },
};

test("independent obstacle drafts retain physical flags and move without a level lookup", async () => {
  const { descriptor, model, placement, review } = await authorObstacleDraft(shape, options);
  assert.equal(review.appearanceComplete, false);
  assert.equal(review.masksComplete, false);
  const gltf = await new NodeIO().readBinary(model);
  assert.equal(gltf.getRoot().listMeshes().length, 1);
  assert.equal(gltf.getRoot().listTextures().length, 0);
  assert.equal(gltf.getRoot().listMeshes()[0]!.listPrimitives()[0]!.getIndices()!.getCount(), 36);
  const { document, assets } = assetCompilerFixture();
  assets.set(descriptor.id, descriptor);
  document.objects.push(placement);
  const compile = () => compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const canopies = () => compile().sight_obstacles.filter((o) => o.points[0]!.z_bottom === 30);
  assert.equal(canopies().length, 1);
  const original = canopies()[0]!;
  for (const key of [
    "points",
    "solid",
    "opaque",
    "mouse",
    "show_shadow_polygon",
    "default_material",
  ] as const)
    assert.deepEqual(original[key], shape[key]);
  placement.transform.dx += 100;
  assert.deepEqual(
    canopies()[0]!.points,
    shape.points.map((p) => ({ ...p, x: p.x + 100 })),
  );
  const copy = structuredClone(placement);
  copy.id = "copy";
  copy.transform.dx += 100;
  document.objects.push(copy);
  assert.equal(canopies().length, 2);
  assert.ok(
    canopies().some(
      (o) =>
        JSON.stringify(o.points) ===
        JSON.stringify(shape.points.map((p) => ({ ...p, x: p.x + 200 }))),
    ),
  );
  assert.deepEqual(shape.points[0], { x: 600, y: 600, z_bottom: 30, z_top: 32 });
});

test("obstacle drafts reject receiving metadata and invalid physical volumes", async () => {
  await assert.rejects(
    authorObstacleDraft({ ...shape, projection_area: [1, 2] }, options),
    /separate authoring/,
  );
  await assert.rejects(
    authorObstacleDraft({ ...shape, material_indices: [2] }, options),
    /separate authoring/,
  );
  await assert.rejects(
    authorObstacleDraft(
      { ...shape, points: [{ x: 0, y: 0, z_bottom: 5, z_top: 1 }, ...shape.points] },
      options,
    ),
    /ordered volume/,
  );
  await assert.rejects(authorObstacleDraft(shape, { ...options, id: "../bad" }), /stable ID/);
});
