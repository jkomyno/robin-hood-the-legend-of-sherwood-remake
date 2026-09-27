import test from "node:test";
import assert from "node:assert/strict";
import { decode } from "fast-png";
import { unzipSync, strFromU8 } from "fflate";
import * as THREE from "three";
import { type Level3D, gameToScene, parseStoredMap } from "@rle/shared";
import { compileMap, packageCompiledMap, validateBakeBounds } from "./map-compile.ts";
import { bakeScene, contentBakeBounds } from "./map-bake-render.ts";
import {
  assetCompilerFixture,
  slopedAssetCompilerFixture,
  liftAssetCompilerFixture,
  interiorAssetCompilerFixture,
  clearanceAssetCompilerFixture,
  materialAssetCompilerFixture,
} from "../../shared/test-fixtures/asset-gameplay.ts";
import { readFile } from "node:fs/promises";

test("asset material export matches the native lookup fixture", async () => {
  const { document, assets } = materialAssetCompilerFixture();
  const fixture = JSON.parse(
    await readFile(
      new URL(
        "../../../crates/robin_engine/tests/fixtures/asset-material.level.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  assert.deepEqual(compileMap(document, [0, 0, 2000, 2000], assets).descriptor, fixture);
});

test("asset-local movement clearance export matches the native navigation fixture", async () => {
  const { document, assets } = clearanceAssetCompilerFixture();
  const fixture = JSON.parse(
    await readFile(
      new URL(
        "../../../crates/robin_engine/tests/fixtures/asset-clearance.level.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  assert.deepEqual(compileMap(document, [0, 0, 2000, 2000], assets).descriptor, fixture);
});

export function bakeFixture(): Level3D {
  return {
    version: 1,
    map: "Bake Contract",
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    sceneAssets: [],
    size: [128, 128],
    groups: [{ id: "house", transform: { dx: 5, dy: 10, dz: 0, rot_deg: 0 } }],
    objects: [
      {
        id: "wall",
        node: "wall",
        kind: "building",
        source: { map: "Bake Contract", obstacle: 0 },
        group: "house",
        transform: { dx: 3, dy: 2, dz: 0, rot_deg: 0 },
        obstacle: {
          points: [
            [0, 0],
            [20, 0],
            [20, 20],
            [0, 20],
          ].map(([x, y]) => ({ x: x!, y: y!, z_bottom: 0, z_top: 30 })),
          opaque: true,
          solid: true,
          mouse: true,
          projection_area: null,
          show_shadow_polygon: false,
          default_material: 0,
          material_indices: [],
        },
      },
    ],
  };
}

test("compilation rebases transformed volumes, namespaces output and preserves the document", () => {
  const document = bakeFixture(),
    before = structuredClone(document);
  const result = compileMap(document, [-20, -10, 128, 128]);
  assert.equal(result.name, "editor-bake-contract");
  assert.deepEqual(result.descriptor.volumes[0]!.footprint, [
    [28, 22],
    [48, 22],
    [48, 42],
    [28, 42],
  ]);
  assert.equal(result.descriptor.volumes[0]!.motion_blocking, true);
  assert.deepEqual(document, before);
  document.groups[0]!.hidden = true;
  assert.deepEqual(compileMap(document, [0, 0, 128, 128]).descriptor.volumes, []);
});

test("map export does not invent mission spawns, even for a tiny frame", () => {
  const result = compileMap(bakeFixture(), [0, 0, 8, 8]);
  assert.equal(result.descriptor.spawn_player, false);
  assert.equal("spawn" in result.descriptor, false);
  assert.equal("reveal_all" in result.descriptor, false);
});

test("bounds round outward, reject unsafe sizes, and fit visible geometry only", () => {
  assert.deepEqual(validateBakeBounds([-0.5, -1.5, 100, 100]), [-1, -2, 101, 101]);
  for (const bounds of [
    [0, 0, 0, 1],
    [0, 0, 17000, 1],
    [0, 0, 16384, 16384],
    [NaN, 0, 1, 1],
  ])
    assert.throws(() => validateBakeBounds(bounds as [number, number, number, number]));
  const camera = bakeFixture().camera;
  const root = new THREE.Group();
  const geometry = new THREE.BufferGeometry().setFromPoints(
    [
      [0, 0, 0],
      [100, 0, 0],
      [0, 100, 0],
    ].map((p) => new THREE.Vector3(...gameToScene(camera, p[0]!, p[1]!, p[2]!))),
  );
  root.add(new THREE.Mesh(geometry, new THREE.MeshBasicMaterial()));
  const hidden = new THREE.Mesh(new THREE.BoxGeometry(10000, 10000, 10000));
  hidden.visible = false;
  root.add(hidden);
  const bounds = contentBakeBounds(root, camera);
  assert.ok(bounds[2] <= 101 && bounds[3] <= 101);
  geometry.dispose();
  hidden.geometry.dispose();
});

test("bake snapshot resets patch previews without changing editor objects", () => {
  const root = new THREE.Group(),
    node = new THREE.Group();
  node.userData = { reveal_material_patch: "p", reveal_material_state: "covered" };
  node.visible = false;
  root.add(node);
  const snapshot = bakeScene([root]);
  assert.equal(snapshot.children[0]!.children[0]!.visible, true);
  assert.equal(node.visible, false);
});

test("mod ZIP has root metadata, a playable descriptor and lossless 16-bit depth", async () => {
  const document = bakeFixture();
  document.notes = "Unsaved authoring notes";
  document.exportBounds = [-10, -20, 128, 128];
  const expectedDocument = structuredClone(document);
  const compiled = compileMap(document, [0, 0, 128, 128]);
  document.notes = "Edited after compilation";
  const color = new Uint8Array(128 * 128 * 4).fill(255);
  const depth = Uint16Array.from({ length: 128 * 128 }, (_, i) => i * 4);
  const bytes = await packageCompiledMap(compiled, { color, depth });
  const files = unzipSync(bytes),
    prefix = "Data/Levels/Day/editor-bake-contract";
  assert.deepEqual(JSON.parse(strFromU8(files["details.json"]!)).hackable_missions, [
    compiled.name,
  ]);
  assert.deepEqual(
    JSON.parse(strFromU8(files[`Data/Levels/${compiled.name}.level.json`]!)),
    compiled.descriptor,
  );
  const editable = JSON.parse(strFromU8(files[`editor/${compiled.name}.rhlos-map.json`]!));
  assert.deepEqual(parseStoredMap(editable, new Map()), expectedDocument);
  const decoded = decode(files[`${prefix}.occlusion-depth.png`]!);
  assert.equal(decoded.depth, 16);
  assert.equal(decoded.channels, 1);
  assert.deepEqual(decoded.data, depth);
  assert.equal(decode(files[`${prefix}.map.png`]!).width, 128);
  assert.equal(decode(files[`${prefix}.min.png`]!).width, 9);
  await assert.rejects(
    packageCompiledMap(compiled, { color: new Uint8Array(), depth }),
    /dimensions/,
  );
});

test("asset export retains a reopenable pinned scene and matches the Rust runtime fixture", async () => {
  const { document, assets } = assetCompilerFixture();
  const runtimeFixture = compileMap(document, [0, 0, 2000, 2000], assets);
  const fixture = JSON.parse(
    await readFile(
      new URL(
        "../../../crates/robin_engine/tests/fixtures/asset-compiled.level.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  assert.deepEqual(runtimeFixture.descriptor, fixture);
  const expected = structuredClone(document);
  const compiled = compileMap(document, [0, 0, 512, 512], assets);
  const bytes = await packageCompiledMap(compiled, {
    color: new Uint8Array(512 * 512 * 4),
    depth: new Uint16Array(512 * 512),
  });
  const files = unzipSync(bytes);
  const reopened = parseStoredMap(
    JSON.parse(strFromU8(files[`editor/${compiled.name}.rhlos-map.json`]!)),
    assets,
  );
  assert.deepEqual(reopened, expected);
});

test("sloped asset export matches the native elevation/navigation fixture", async () => {
  const { document, assets } = slopedAssetCompilerFixture();
  const fixture = JSON.parse(
    await readFile(
      new URL(
        "../../../crates/robin_engine/tests/fixtures/asset-sloped.level.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  assert.deepEqual(compileMap(document, [0, 0, 2000, 2000], assets).descriptor, fixture);
});

test("lift asset export matches the native traversal fixture", async () => {
  const { document, assets } = liftAssetCompilerFixture();
  const fixture = JSON.parse(
    await readFile(
      new URL("../../../crates/robin_engine/tests/fixtures/asset-lift.level.json", import.meta.url),
      "utf8",
    ),
  );
  assert.deepEqual(compileMap(document, [0, 0, 2000, 2000], assets).descriptor, fixture);
});

test("interior asset export matches the native building fixture", async () => {
  const { document, assets } = interiorAssetCompilerFixture();
  const fixture = JSON.parse(
    await readFile(
      new URL(
        "../../../crates/robin_engine/tests/fixtures/asset-interior.level.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  assert.deepEqual(compileMap(document, [0, 0, 2000, 2000], assets).descriptor, fixture);
});
