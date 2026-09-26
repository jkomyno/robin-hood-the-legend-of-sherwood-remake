import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";
import { SceneAssetLoader } from "./scene-assets.ts";
import { parseLevel3D, type SceneAssetSource } from "@rle/shared";

const hash = (bytes: Uint8Array | string) => createHash("sha256").update(bytes).digest("hex");
function fixture() {
  const files = new Map<string, File>();
  const reads = new Map<string, number>();
  const root = (prefix = ""): FileSystemDirectoryHandle => ({
    async getDirectoryHandle(name: string) { return root(prefix + name + "/"); },
    async getFileHandle(name: string) {
      const key = prefix + name;
      reads.set(key, (reads.get(key) ?? 0) + 1);
      if (!files.has(key)) throw new Error("Missing " + key);
      return { getFile: async () => files.get(key)! };
    },
  }) as unknown as FileSystemDirectoryHandle;
  const model = JSON.stringify({ asset: { version: "2.0" }, scenes: [{ nodes: [] }], scene: 0, nodes: [] });
  const reference: SceneAssetSource = { id: "house", role: "objects", model: "3d-assets/house.gltf", model_sha256: hash(model),
    resources: [{ path: "3d-assets/texture.png", sha256: hash("texture") }] };
  files.set(reference.model, new File([model], "house.gltf"));
  files.set(reference.resources[0]!.path, new File(["texture"], "texture.png"));
  return { files, reads, reference, loader: new SceneAssetLoader(root()) };
}

test("pinned resources are read once and shared across asset loads", async t => {
  const f = fixture();
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: new THREE.Group() }));
  await f.loader.load(f.reference); await f.loader.load({ ...f.reference, id: "second-house" });
  assert.equal(f.reads.get("3d-assets/texture.png"), 1);
  f.loader.dispose();
});

test("changed models and resource bytes fail before decoding", async t => {
  const f = fixture();
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => { throw new Error("Unexpected decode"); });
  await assert.rejects(f.loader.load({ ...f.reference, model_sha256: "f".repeat(64) }), /Scene asset changed/);
  f.files.set("3d-assets/texture.png", new File(["edited"], "texture.png"));
  await assert.rejects(f.loader.load(f.reference), /Scene asset changed/);
  f.loader.dispose();
});

test("map manifests reject old whole-map storage and unsafe asset references", () => {
  const document = { version: 1, map: "Empty", size: null, camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    sceneAssets: [], objects: [], groups: [] };
  assert.throws(() => parseLevel3D({ ...document, glb: "map.glb" }), /must be imported/);
  const reference = fixture().reference;
  for (const asset of [{ ...reference, model: "../outside.gltf" }, { ...reference, role: "unknown" },
    { ...reference, resources: [...reference.resources, ...reference.resources] }])
    assert.throws(() => parseLevel3D({ ...document, sceneAssets: [asset] }));
});

test("ground lossy models load in place of their pinned GLB only with a matching receipt", async t => {
  const files = new Map<string, File>();
  const root = (prefix = ""): FileSystemDirectoryHandle => ({
    async getDirectoryHandle(name: string) { return root(prefix + name + "/"); },
    async getFileHandle(name: string) {
      if (!files.has(prefix + name)) throw new DOMException(prefix + name, "NotFoundError");
      return { getFile: async () => files.get(prefix + name)! };
    },
  }) as unknown as FileSystemDirectoryHandle;
  const published = new Uint8Array([1, 2, 3]), lossy = new Uint8Array([7]);
  const reference: SceneAssetSource = { id: "terrain", role: "ground", model: "3d-assets/terrain/model.glb", model_sha256: hash(published), resources: [] };
  files.set("3d-assets/terrain/lossy.glb", new File([lossy], "lossy.glb"));
  files.set("3d-assets/terrain/lossy.glb.receipt.json", new File([JSON.stringify({ source: hash(published), output: hash(lossy) })], "r.json"));
  const loaded: number[][] = [];
  t.mock.method(GLTFLoader.prototype, "parseAsync", async (bytes: ArrayBuffer) => { loaded.push([...new Uint8Array(bytes)]); return { scene: new THREE.Group() }; });
  const loader = new SceneAssetLoader(root(), new Map([[reference.model, "3d-assets/terrain/lossy.glb"]]));
  await loader.load(reference);
  assert.deepEqual(loaded, [[7]]);
  // Stale receipt: fall back to the published model (absent here, so the load fails on it).
  t.mock.method(console, "warn", () => {});
  files.set("3d-assets/terrain/lossy.glb.receipt.json", new File([JSON.stringify({ source: "c".repeat(64), output: hash(lossy) })], "r.json"));
  await assert.rejects(loader.load(reference), /terrain\/model\.glb/);
  files.set(reference.model, new File([published], "model.glb"));
  await loader.load(reference);
  assert.deepEqual(loaded.at(-1), [1, 2, 3]);
  // Without a lossy model entry the pinned model is used unchanged.
  await new SceneAssetLoader(root()).load(reference);
  assert.deepEqual(loaded.at(-1), [1, 2, 3]);
  loader.dispose();
});
