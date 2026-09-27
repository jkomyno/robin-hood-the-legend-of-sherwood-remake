import { test } from "node:test";
import assert from "node:assert/strict";
import { Document, NodeIO } from "@gltf-transform/core";
import {
  IDENTITY_TRANSFORM,
  transformedObstacle,
  type Level3D,
  type ProjectionAssetDescriptor,
} from "@rle/shared";
import { mergeStaticAssets } from "./merge-static-assets.ts";
import { splitStaticAsset } from "./split-static-asset.ts";

function fixture() {
  const document: Level3D = {
    version: 1,
    map: "fixture",
    size: [1000, 1000],
    sceneAssets: [],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    groups: [],
    objects: [],
    assetSources: [],
  };
  const inputs = [0, 1].map((index) => {
    const id = `piece-${index}`;
    const node = `building-${index}`;
    const obstacle = {
      points: [
        [0, 0],
        [10, 0],
        [10, 10],
      ].map(([x, y]) => ({ x: x!, y: y!, z_bottom: 0, z_top: 10 })),
      projection_area: null,
      opaque: true,
      solid: true,
      mouse: true,
      show_shadow_polygon: true,
      default_material: 0,
      material_indices: [],
    };
    const descriptor: ProjectionAssetDescriptor = {
      version: 1,
      kind: "projection-mapped-asset",
      id,
      name: id,
      source_map: "fixture",
      model: "model.glb",
      model_scene: "default",
      parts: [{ node, name: node, source_obstacle: index, obstacle_local_game: obstacle }],
    };
    document.groups.push({
      id,
      transform: {
        dx: 100 + index * 20,
        dy: 100 + index * 40,
        dz: index * 10,
        rot_deg: 0,
      },
    });
    document.objects.push({
      id: node,
      node: `asset:${id}:${node}`,
      kind: "building",
      group: id,
      source: { map: "fixture", obstacle: index },
      obstacle,
      transform: { ...IDENTITY_TRANSFORM },
    });
    const model = new Document();
    const buffer = model.createBuffer();
    const positions = model
      .createAccessor()
      .setBuffer(buffer)
      .setType("VEC3")
      .setArray(new Float32Array([0, 0, 0, 10, 0, 0, 10, 0, -10]));
    const mesh = model
      .createMesh()
      .addPrimitive(model.createPrimitive().setAttribute("POSITION", positions));
    model.createScene("default").addChild(model.createNode(node).setMesh(mesh));
    return { descriptor, model };
  });
  return { document, inputs };
}

test("canonical merge preserves world collisions, raw vertex data, and relative placement", async () => {
  const { document, inputs } = fixture();
  const before = document.objects.map((part) => transformedObstacle(document, part));
  const merged = await mergeStaticAssets(document, "whole-building", [0, 1], inputs);
  assert.deepEqual(
    merged.document.objects.map((part) => transformedObstacle(merged.document, part)),
    before,
  );
  assert.equal(merged.document.groups.length, 1);
  const model = await new NodeIO().readBinary(merged.bytes);
  const map = model.getRoot().getDefaultScene()!.listChildren()[0]!;
  assert.equal(map.getName(), "map");
  assert.equal(map.listChildren().length, 1);
  const group = map.listChildren()[0]!;
  assert.deepEqual(group.getExtras(), { asset_group: "whole-building" });
  assert.deepEqual(group.getTranslation(), [0, 0, 0]);
  assert.deepEqual(
    group.listChildren().map((node) => node.getName()),
    ["building-0", "building-1"],
  );
  assert.equal(model.getRoot().listMeshes().length, 2);
  for (const accessor of model.getRoot().listAccessors())
    assert.deepEqual(Array.from(accessor.getArray()!), [0, 0, 0, 10, 0, 0, 10, 0, -10]);
  const second = model
    .getRoot()
    .listNodes()
    .find((node) => node.getName() === "building-1")!;
  assert.ok(Math.abs(second.getWorldMatrix()[12]! - 20) < 1e-9);
  assert.ok(Math.abs(second.getWorldMatrix()[13]! - 10 / Math.cos((35 * Math.PI) / 180)) < 1e-9);
  assert.ok(Math.abs(second.getWorldMatrix()[14]! - 40 / Math.sin((35 * Math.PI) / 180)) < 1e-9);
  merged.document.groups[0]!.transform.dx += 200;
  for (const [index, part] of merged.document.objects.entries())
    assert.equal(
      transformedObstacle(merged.document, part).points[0]!.x,
      before[index]!.points[0]!.x + 200,
    );
  assert.equal(document.groups.length, 2);
});

test("partial catalog membership and edited placements cannot silently lose data", async () => {
  const { document, inputs } = fixture();
  await assert.rejects(mergeStaticAssets(document, "whole-building", [0], inputs), /membership/);
  document.objects[1]!.transform.dx = 2;
  await assert.rejects(
    mergeStaticAssets(document, "whole-building", [0, 1], inputs),
    /Unsupported/,
  );
});

test("editor normalization preserves transformed parts and rejects unowned model content", async () => {
  const { document, inputs } = fixture();
  const model = inputs[0]!.model;
  const scene = model.getRoot().listScenes()[0]!;
  const part = scene.listChildren()[0]!;
  const wrapper = model
    .createNode("parent")
    .setTranslation([12, 34, 56])
    .setRotation([0, 0, Math.sin(0.3), Math.cos(0.3)])
    .setScale([2, 2, 2]);
  wrapper.addChild(part);
  scene.addChild(wrapper);
  const world = part.getWorldMatrix();
  const merged = await mergeStaticAssets(document, "whole-building", [0, 1], inputs);
  const result = await new NodeIO().readBinary(merged.bytes);
  const after = result
    .getRoot()
    .listNodes()
    .find((node) => node.getName() === "building-0")!
    .getWorldMatrix();
  for (const [index, value] of world.entries()) assert.ok(Math.abs(value - after[index]!) < 1e-9);
  const invalid = fixture();
  const unowned = invalid.inputs[0]!.model.createNode("unowned").setMesh(
    invalid.inputs[0]!.model.getRoot().listMeshes()[0]!,
  );
  invalid.inputs[0]!.model.getRoot().listScenes()[0]!.addChild(unowned);
  await assert.rejects(
    mergeStaticAssets(invalid.document, "whole-building", [0, 1], invalid.inputs),
    /Unowned model content/,
  );
});

test("stateful assets require explicit migration", async () => {
  const { document, inputs } = fixture();
  inputs[1]!.descriptor.states = { active: "initial", initial: ["building-1"], applied: [] };
  await assert.rejects(mergeStaticAssets(document, "whole-building", [0, 1], inputs), /migration/);
});

test("split preserves nested model transforms and assigns every part once", async () => {
  const { document, inputs } = fixture();
  const merged = await mergeStaticAssets(document, "whole-building", [0, 1], inputs);
  const source = {
    descriptor: merged.descriptor,
    model: await new NodeIO().readBinary(merged.bytes),
  };
  const split = await splitStaticAsset(merged.document, source, [
    { id: "stone-shop", obstacles: [0] },
    { id: "timber-house", obstacles: [1] },
  ]);
  assert.deepEqual(
    split.document.objects.map((part) => transformedObstacle(split.document, part)),
    document.objects.map((part) => transformedObstacle(document, part)),
  );
  assert.deepEqual(
    split.outputs.map((output) => output.descriptor.parts.map((part) => part.source_obstacle)),
    [[0], [1]],
  );
  for (const [index, output] of split.outputs.entries()) {
    const map = output.model.getRoot().listScenes()[0]!.listChildren()[0]!;
    assert.equal(map.getName(), "map");
    assert.equal(map.listChildren().length, 1);
    assert.deepEqual(map.listChildren()[0]!.getExtras(), { asset_group: output.descriptor.id });
    const rendered: string[] = [];
    output.model
      .getRoot()
      .listScenes()[0]!
      .traverse((node) => {
        if (node.getMesh()) rendered.push(node.getName());
      });
    assert.deepEqual(rendered, [`building-${index}`]);
  }
  const house = split.document.groups.find((group) => group.id === "timber-house")!;
  house.transform.dx += 200;
  assert.equal(transformedObstacle(split.document, split.document.objects[0]!).points[0]!.x, 100);
  assert.equal(transformedObstacle(split.document, split.document.objects[1]!).points[0]!.x, 320);
  await assert.rejects(
    splitStaticAsset(merged.document, source, [
      { id: "stone-shop", obstacles: [0] },
      { id: "timber-house", obstacles: [0] },
    ]),
    /every part exactly once/,
  );
  source.model
    .getRoot()
    .listNodes()
    .find((node) => node.getName() === "building-1")!
    .setName("unowned");
  await assert.rejects(
    splitStaticAsset(merged.document, source, [
      { id: "stone-shop", obstacles: [0] },
      { id: "timber-house", obstacles: [1] },
    ]),
    /every rendered node/,
  );
});
