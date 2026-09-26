import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { Document, NodeIO } from "@gltf-transform/core";
import { generatePreview, previewFingerprint, previewTextureSize } from "./preview-model.ts";

test("preview texture edge follows source texels: /8, multiple of 16, clamped 32-512", () => {
  assert.equal(previewTextureSize(112 * 112), 32);
  assert.equal(previewTextureSize(848 * 848), 112);
  assert.equal(previewTextureSize(3184 * 3184), 400);
  assert.equal(previewTextureSize(2944 * 2176), 320);
  assert.equal(previewTextureSize(8192 * 8192), 512);
  assert.throws(() => previewTextureSize(0), /no texture/);
});

test("CLI writes a meshopt-compressed preview GLB deterministically; fingerprint is stable", async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "preview-model-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const doc = new Document();
  const buffer = doc.createBuffer();
  const positions = doc.createAccessor().setType("VEC3").setArray(new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0])).setBuffer(buffer);
  const indices = doc.createAccessor().setType("SCALAR").setArray(new Uint16Array([0, 1, 2])).setBuffer(buffer);
  const primitive = doc.createPrimitive().setAttribute("POSITION", positions).setIndices(indices);
  doc.createScene().addChild(doc.createNode().setMesh(doc.createMesh().addPrimitive(primitive)));
  const input = path.join(root, "model.glb");
  await new NodeIO().write(input, doc);
  const run = promisify(execFile);
  const script = new URL("./preview-model.ts", import.meta.url).pathname;
  const first = JSON.parse((await run(process.execPath, [script, input, path.join(root, "a.glb")])).stdout.trim().split("\n").at(-1)!);
  const second = JSON.parse((await run(process.execPath, [script, input, path.join(root, "b.glb")])).stdout.trim().split("\n").at(-1)!);
  assert.equal(first.edge, null);
  assert.equal(first.sha256, second.sha256);
  const bytes = await fs.readFile(path.join(root, "a.glb"));
  assert.equal(bytes.toString("ascii", 0, 4), "glTF");
  const json = JSON.parse(bytes.toString("utf8", 20, 20 + bytes.readUInt32LE(12)));
  assert.ok(json.extensionsUsed.includes("EXT_meshopt_compression"));
  assert.equal((await generatePreview(input)).bytes.length, bytes.length);
  assert.equal(await previewFingerprint(), await previewFingerprint());
});
