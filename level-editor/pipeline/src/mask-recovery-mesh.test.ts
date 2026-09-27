import test from "node:test";
import assert from "node:assert/strict";
import { Document } from "@gltf-transform/core";
import { maskRecoveryMesh } from "./mask-recovery-mesh.ts";

function fixture(indexed = true) {
  const model = new Document();
  const buffer = model.createBuffer();
  const positions = model
    .createAccessor()
    .setBuffer(buffer)
    .setType("VEC3")
    .setArray(new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]));
  const primitive = model.createPrimitive().setAttribute("POSITION", positions);
  if (indexed)
    primitive.setIndices(
      model
        .createAccessor()
        .setBuffer(buffer)
        .setType("SCALAR")
        .setArray(new Uint16Array([2, 1, 0])),
    );
  const mesh = model.createMesh().addPrimitive(primitive);
  const child = model
    .createNode("mesh")
    .setTranslation([0, 2, 0])
    .setScale([2, 3, 1])
    .setMesh(mesh);
  const part = model.createNode("part").setTranslation([10, 0, 0]).addChild(child);
  const scene = model.createScene().addChild(part);
  model.getRoot().setDefaultScene(scene);
  return { model, primitive, part, scene };
}

test("mesh recovery applies descendant and parent transforms for indexed and raw triangles", () => {
  for (const indexed of [true, false]) {
    const { model } = fixture(indexed);
    const triangle = maskRecoveryMesh(model, "part", ([x, y, z]) => [x + 100, y, z])[0]!;
    const expected = [
      [110, 2, 0],
      [112, 2, 0],
      [110, 5, 0],
    ];
    assert.deepEqual(triangle, indexed ? expected.reverse() : expected);
  }
});

test("mesh recovery requires an unambiguous part in the selected scene", () => {
  const { model, scene } = fixture();
  model.createNode("part"); // An unreachable node is not a duplicate in this state.
  assert.equal(maskRecoveryMesh(model, "part", (p) => p).length, 1);
  assert.throws(() => maskRecoveryMesh(model, "missing", (p) => p), /one selected part/);
  scene.addChild(model.createNode("part"));
  assert.throws(() => maskRecoveryMesh(model, "part", (p) => p), /one selected part/);
});

test("mesh recovery rejects unsupported coverage and malformed geometry", () => {
  for (const alpha of ["MASK", "BLEND"] as const) {
    const { model, primitive } = fixture();
    primitive.setMaterial(model.createMaterial().setAlphaMode(alpha));
    assert.throws(() => maskRecoveryMesh(model, "part", (p) => p), /texture coverage/);
  }
  const { model, primitive } = fixture();
  primitive.getIndices()!.setArray(new Uint16Array([0, 1, 20]));
  assert.throws(() => maskRecoveryMesh(model, "part", (p) => p), /outside positions/);
  primitive.getIndices()!.setArray(new Uint16Array([0, 1]));
  assert.throws(() => maskRecoveryMesh(model, "part", (p) => p), /incomplete triangles/);
  primitive.getIndices()!.setArray(new Uint16Array([0, 1, 2]));
  assert.throws(() => maskRecoveryMesh(model, "part", () => [NaN, 0, 0]), /Invalid placed/);
  model.createAnimation();
  assert.throws(() => maskRecoveryMesh(model, "part", (p) => p), /static model state/);
});
