import test from "node:test";
import assert from "node:assert/strict";
import {
  parseExternalAssetSources,
  parseProjectionAssetDescriptor,
  parseProjectionAssetIndex,
  parseLevel3D,
} from "./validation.ts";
import { assetNodeKey, safeLibraryPath } from "./projection-assets.ts";

const obstacle = {
  points: [
    { x: 0, y: 0, z_bottom: 0, z_top: 10 },
    { x: 10, y: 0, z_bottom: 0, z_top: 10 },
    { x: 0, y: 10, z_bottom: 0, z_top: 10 },
  ],
  opaque: true,
  solid: true,
  mouse: true,
  show_shadow_polygon: true,
  default_material: 0,
  material_indices: [],
  projection_area: null,
};
const descriptor = {
  version: 1,
  kind: "projection-mapped-asset",
  id: "house",
  name: "House",
  source_map: "Leicester",
  model: "model.glb",
  source_origin_scene: [20, -40, 0],
  source_origin_game: [20, 23, 0],
  parts: [
    {
      node: "building-000",
      name: "Wall",
      source_obstacle: 0,
      obstacle_local_game: obstacle,
      default_hidden: true,
    },
  ],
};
const reference = {
  id: "house",
  descriptor: "3d-assets/house/asset.json",
  model: "3d-assets/house/model.glb",
  descriptor_sha256: "a".repeat(64),
  model_sha256: "b".repeat(64),
};

test("projection descriptors retain extras and state defaults while validating local parts", () => {
  const value = { ...descriptor, reveal: { source: "evidence" } };
  assert.equal(parseProjectionAssetDescriptor(value), value);
  assert.throws(
    () =>
      parseProjectionAssetDescriptor({
        ...descriptor,
        parts: [...descriptor.parts, ...descriptor.parts],
      }),
    /duplicate/,
  );
  assert.throws(
    () =>
      parseProjectionAssetDescriptor({
        ...descriptor,
        parts: [{ ...descriptor.parts[0], source_obstacle: 1 }],
      }),
    /canonical/,
  );
  assert.throws(
    () =>
      parseProjectionAssetDescriptor({
        ...descriptor,
        parts: [{ ...descriptor.parts[0], default_hidden: "yes" }],
      }),
    /default_hidden/,
  );
  assert.throws(
    () => parseProjectionAssetDescriptor({ ...descriptor, model: "../model.glb" }),
    /safe/,
  );
  assert.throws(
    () => parseProjectionAssetDescriptor({ ...descriptor, source_origin_scene: [0, Infinity, 0] }),
    /source_origin_scene/,
  );
});

test("library paths and identities reject traversal and duplicate source records", () => {
  for (const path of ["../a", "/a", "a//b", "a/./b", "C:/a", "a\\b", "a?x", "a%2fb", "a#x"])
    assert.equal(safeLibraryPath(path), false, path);
  assert.equal(safeLibraryPath("3d-assets/house/model.glb"), true);
  assert.equal(parseExternalAssetSources([reference])[0], reference);
  assert.throws(() => parseExternalAssetSources([reference, reference]), /duplicate/);
  assert.throws(
    () => parseExternalAssetSources([{ ...reference, model_sha256: "bad" }]),
    /SHA-256/,
  );
  assert.throws(
    () =>
      parseProjectionAssetIndex({
        version: 1,
        assets: [
          {
            id: "house",
            name: "House",
            source_map: "Leicester",
            descriptor: "../asset.json",
            model: "model.glb",
          },
        ],
      }),
    /safe/,
  );
});

test("documents preserve pinned external sources and reject dangling namespaces", () => {
  const document = {
    version: 1,
    map: "Leicester",
    sceneAssets: [],
    size: [100, 100],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    groups: [],
    assetSources: [reference],
    objects: [
      {
        id: "copy",
        node: assetNodeKey("house", "building-000"),
        kind: "building",
        source: { map: "Leicester", obstacle: 0 },
        obstacle,
        transform: { dx: 0, dy: 0, dz: 0, rot_deg: 0 },
      },
    ],
  };
  assert.equal(parseLevel3D(document).assetSources?.[0], reference);
  assert.throws(() => parseLevel3D({ ...document, assetSources: [] }), /dangling external/);
  assert.equal(
    parseLevel3D({ ...document, assetSources: undefined, objects: [] }).assetSources,
    undefined,
  );
});

test("only explicit ground-only map backgrounds may have no editable parts", () => {
  const ground = {
    ...descriptor,
    editor_usage: "map-background",
    parts: [],
    components: [{ source_node: "ground" }],
  };
  assert.equal(parseProjectionAssetDescriptor(ground), ground);
  assert.throws(() => parseProjectionAssetDescriptor({ ...descriptor, parts: [] }), /nonempty/);
  assert.throws(
    () =>
      parseProjectionAssetDescriptor({ ...ground, components: [{ source_node: "building-001" }] }),
    /ground-only/,
  );
  assert.throws(
    () => parseProjectionAssetDescriptor({ ...ground, parts: descriptor.parts }),
    /cannot contain/,
  );
});

test("static variants require safe model paths and validated endpoint parts", () => {
  const variants = {
    initial: { name: "Raised", model: "raised.glb" },
    applied: { name: "Lowered", model: "lowered.glb" },
  };
  assert.doesNotThrow(() =>
    parseProjectionAssetDescriptor({ ...descriptor, state_variants: variants }),
  );
  for (const state_variants of [
    {},
    { unknown: variants.initial },
    { initial: { ...variants.initial, model: "../escape.glb" } },
    { initial: { ...variants.initial, parts: [] } },
  ]) {
    assert.throws(() => parseProjectionAssetDescriptor({ ...descriptor, state_variants }));
  }
  assert.throws(() => parseExternalAssetSources([{ ...reference, state_variant: "moving" }]));
});

test("mission descriptor parts require explicit profile provenance and prohibit obstacle ownership", () => {
  const { source_obstacle: _source_obstacle, ...base } = descriptor.parts[0]!;
  const mission = {
    ...base,
    node: "mission-second-drawbridge",
    mission_profile: "Derby - Pont_levis02",
  };
  assert.doesNotThrow(() => parseProjectionAssetDescriptor({ ...descriptor, parts: [mission] }));
  for (const part of [
    { ...mission, source_obstacle: 267 },
    { ...mission, mission_profile: "" },
    { ...mission, mission_profile: undefined },
    { ...mission, node: "building-267" },
  ]) {
    assert.throws(() => parseProjectionAssetDescriptor({ ...descriptor, parts: [part] }));
  }
});

test("split obstacle descriptors require scoped identity and disjoint ownership", () => {
  const part = {
    ...descriptor.parts[0],
    node: "building-000--component-west",
    source_components: ["west"],
  };
  assert.doesNotThrow(() =>
    parseProjectionAssetDescriptor({
      ...descriptor,
      parts: [part, { ...part, node: "building-000--component-east", source_components: ["east"] }],
    }),
  );
  for (const wrong of [
    { ...part, source_components: undefined },
    { ...part, source_components: ["east"] },
    { ...part, node: "building-000" },
  ])
    assert.throws(
      () => parseProjectionAssetDescriptor({ ...descriptor, parts: [wrong] }),
      /canonical/,
    );
  assert.throws(
    () => parseProjectionAssetDescriptor({ ...descriptor, parts: [part, descriptor.parts[0]] }),
    /duplicate/,
  );
  const document = {
    version: 1,
    map: "Leicester",
    sceneAssets: [],
    size: [100, 100],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    groups: [],
    assetSources: [reference],
    objects: [
      {
        id: "copy",
        node: assetNodeKey("house", part.node),
        kind: "building",
        source: { map: "Leicester", obstacle: 0, components: ["west"] },
        obstacle,
        transform: { dx: 0, dy: 0, dz: 0, rot_deg: 0 },
      },
    ],
  };
  assert.doesNotThrow(() => parseLevel3D(document));
  document.objects[0]!.source.components = ["east"];
  assert.throws(() => parseLevel3D(document), /canonical/);
});

test("additional standalone variants retain a separate primary and reject ambiguous catalogs", () => {
  const variants = {
    initial: { name: "Closed", model: "closed.glb" },
    applied: { name: "Open", model: "open.glb", parts: descriptor.parts },
  };
  assert.doesNotThrow(() =>
    parseProjectionAssetDescriptor({ ...descriptor, standalone_variants: variants }),
  );
  assert.throws(
    () =>
      parseProjectionAssetDescriptor({
        ...descriptor,
        state_variants: variants,
        standalone_variants: variants,
      }),
    /cannot combine/,
  );
  for (const standalone_variants of [
    {},
    { other: variants.initial },
    { initial: { ...variants.initial, model: "../outside.glb" } },
    { initial: { ...variants.initial, parts: [] } },
  ])
    assert.throws(() => parseProjectionAssetDescriptor({ ...descriptor, standalone_variants }));
});
