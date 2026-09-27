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

test("stateful assets require explicit migration", async () => {
  const { document, inputs } = fixture();
  inputs[1]!.descriptor.states = { active: "initial", initial: ["building-1"], applied: [] };
  await assert.rejects(mergeStaticAssets(document, "whole-building", [0, 1], inputs), /migration/);
});
