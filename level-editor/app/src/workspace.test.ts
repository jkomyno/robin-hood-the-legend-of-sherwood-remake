import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createTerrainGrid, parseLevel3D } from "@rle/shared";
import { MAP_SIZE_PRESETS, resizeWorkspace, validateNewMapOptions } from "./workspace.ts";

test("every named reference preset matches its published map dimensions", () => {
  assert.equal(MAP_SIZE_PRESETS.length, 9);
  for (const preset of MAP_SIZE_PRESETS) {
    const document = JSON.parse(
      readFileSync(
        new URL(
          `../../library/scenes/${preset.name.toLowerCase()}.rhlos-map.json`,
          import.meta.url,
        ),
        "utf8",
      ),
    );
    assert.deepEqual(preset.size, document.size, preset.name);
  }
});

test("shrink and regrow retain edited terrain and all out-of-bounds content", () => {
  const terrain = createTerrainGrid([0, 0, 256, 256], 128);
  terrain.vertices[4]!.position = [143, 117, 35];
  terrain.cells[0]!.material = "ground_mud";
  const document = parseLevel3D({
    version: 1,
    map: "Resize",
    size: [256, 256],
    terrain,
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    sceneAssets: [],
    groups: [],
    objects: [],
    exportBounds: [-50, -50, 500, 500],
  });
  const original = structuredClone(document);
  const small = resizeWorkspace(document, [64, 64]);
  assert.strictEqual(small.terrain, document.terrain);
  assert.strictEqual(small.objects, document.objects);
  assert.deepEqual(small.exportBounds, document.exportBounds);
  const restored = resizeWorkspace(small, [256, 256]);
  assert.deepEqual(restored.terrain, document.terrain);
  const enlarged = resizeWorkspace(restored, [512, 384]);
  assert.ok(enlarged.terrain!.cells.length > terrain.cells.length);
  for (const vertex of terrain.vertices)
    assert.deepEqual(
      enlarged.terrain!.vertices.find((entry) => entry.id === vertex.id),
      vertex,
    );
  for (const cell of terrain.cells)
    assert.deepEqual(
      enlarged.terrain!.cells.find((entry) => entry.id === cell.id),
      cell,
    );
  assert.deepEqual(document, original, "Resize must leave the undo source intact");
});

test("invalid and excessive workspace grids fail before allocation", () => {
  for (const size of [
    [0, 128],
    [128.5, 256],
    [NaN, 200],
    [Infinity, 200],
  ])
    assert.throws(() =>
      validateNewMapOptions({ size: size as [number, number], spacing: 128, height: 0 }),
    );
  for (const spacing of [0, -1, NaN, Infinity])
    assert.throws(() => validateNewMapOptions({ size: [128, 128], spacing, height: 0 }));
  assert.throws(
    () => validateNewMapOptions({ size: [1_000_000, 1_000_000], spacing: 1, height: 0 }),
    /250,000/,
  );
});

test("resizing a published ground scene does not add a duplicate flat terrain layer", () => {
  const document = parseLevel3D({
    version: 1,
    map: "Published ground",
    size: [256, 256],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    sceneAssets: [
      {
        id: "ground",
        role: "ground",
        model: "ground/model.glb",
        model_sha256: "a".repeat(64),
        resources: [],
      },
    ],
    groups: [],
    objects: [],
  });
  const resized = resizeWorkspace(document, [512, 512]);
  assert.deepEqual(resized.size, [512, 512]);
  assert.equal(resized.terrain, undefined);
  assert.strictEqual(resized.sceneAssets, document.sceneAssets);
});
