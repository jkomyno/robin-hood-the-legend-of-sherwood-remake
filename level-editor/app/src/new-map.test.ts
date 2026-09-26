import test from "node:test";
import assert from "node:assert/strict";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { parseLevel3D, parseSceneDoc } from "@rle/shared";
import { createNewMap, validateNewMap } from "./new-map.ts";

function fixture(fail?: string) {
  const files = new Map<string, BlobPart>();
  const root = {
    async getDirectoryHandle() { return this; },
    async *entries() { for (const name of files.keys()) yield [name, { kind: "file" }]; },
    async removeEntry(name: string) { files.delete(name); },
    async getFileHandle(name: string) {
      return { async createWritable() {
        return { async write(value: BlobPart) { files.set(name, value); if (name === fail) throw new Error("disk full"); },
          async close() {}, async abort() {} };
      } };
    },
  } as unknown as FileSystemDirectoryHandle;
  return { root, files };
}

test("new maps persist unbounded documents without a required export frame", async t => {
  t.mock.method(GLTFExporter.prototype, "parseAsync", async () => new ArrayBuffer(8));
  const { root, files } = fixture();
  assert.equal(await createNewMap(root, "  New forest  "), "New forest");
  const scene = parseSceneDoc(JSON.parse(String(files.get("New forest-volumes.scene.json"))));
  const doc = parseLevel3D(JSON.parse(String(files.get("New forest.level3d.json"))), { scene });
  assert.equal(scene.size, null);
  assert.equal(scene.standalone, true);
  assert.equal(doc.size, null);
  assert.equal(doc.exportBounds, undefined);
  assert.deepEqual(doc.objects, []);
  assert.deepEqual([...files.keys()], ["New forest-volumes.scene.json", "New forest.level3d.json", "New forest-volumes.scene.glb"]);
});

test("new map creation rejects collisions without overwriting and rolls back failed writes", async t => {
  t.mock.method(GLTFExporter.prototype, "parseAsync", async () => new ArrayBuffer(8));
  const existing = fixture();
  existing.files.set("FOREST.level3d.json", "keep");
  await assert.rejects(createNewMap(existing.root, "forest"), /already exists/);
  assert.deepEqual([...existing.files.values()], ["keep"]);
  const broken = fixture("Forest-volumes.scene.glb");
  await assert.rejects(createNewMap(broken.root, "Forest"), /disk full/);
  assert.equal(broken.files.size, 0);
});

test("map names reject paths and export frames permit negative origins with intentional crops", () => {
  for (const name of ["", "../map", "a/b", "a\\b", "x".repeat(65)]) assert.throws(() => validateNewMap(name));
  const doc = { version: 1, map: "Forest", size: null, camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    glb: "Forest-volumes.scene.glb", groups: [], objects: [], exportBounds: [-200, -400, 800, 600] };
  assert.deepEqual(parseLevel3D(doc).exportBounds, [-200, -400, 800, 600]);
  for (const exportBounds of [[0,0,0,10], [0,0,10,-1], [0,0,10.5,20], [Infinity,0,10,10]])
    assert.throws(() => parseLevel3D({ ...doc, exportBounds }));
  assert.throws(() => parseSceneDoc({ ...doc, placements: [] }), /standalone/);
});
