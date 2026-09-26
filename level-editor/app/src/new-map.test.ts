import test from "node:test";
import assert from "node:assert/strict";
import { parseLevel3D, parseSceneDoc } from "@rle/shared";
import { createNewMap, validateNewMap } from "./new-map.ts";

function fixture(fail?: string) {
  const files = new Map<string, BlobPart>();
  const root = {
    async getDirectoryHandle() {
      return this;
    },
    async *entries() {
      for (const name of files.keys()) yield [name, { kind: "file" }];
    },
    async removeEntry(name: string) {
      files.delete(name);
    },
    async getFileHandle(name: string) {
      return {
        async createWritable() {
          return {
            async write(value: BlobPart) {
              files.set(name, value);
              if (name === fail) throw new Error("disk full");
            },
            async close() {},
            async abort() {},
          };
        },
      };
    },
  } as unknown as FileSystemDirectoryHandle;
  return { root, files };
}

test("new maps persist unbounded documents without a required export frame", async () => {
  const { root, files } = fixture();
  assert.equal(await createNewMap(root, "  New forest  "), "New forest");
  const doc = parseLevel3D(JSON.parse(String(files.get("New forest.rhlos-map.json"))));
  assert.equal(doc.size, null);
  assert.equal(doc.exportBounds, undefined);
  assert.deepEqual(doc.objects, []);
  assert.deepEqual([...files.keys()], ["New forest.rhlos-map.json"]);
});

test("new map creation rejects collisions without overwriting and rolls back failed writes", async () => {
  const existing = fixture();
  existing.files.set("FOREST.rhlos-map.json", "keep");
  await assert.rejects(createNewMap(existing.root, "forest"), /already exists/);
  assert.deepEqual([...existing.files.values()], ["keep"]);
  const broken = fixture("Forest.rhlos-map.json");
  await assert.rejects(createNewMap(broken.root, "Forest"), /Cannot write Forest/);
  assert.equal(broken.files.size, 0);
});

test("map names reject paths and export frames permit negative origins with intentional crops", () => {
  for (const name of ["", "../map", "a/b", "a\\b", "x".repeat(65)])
    assert.throws(() => validateNewMap(name));
  const doc = {
    version: 1,
    map: "Forest",
    size: null,
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    sceneAssets: [],
    groups: [],
    objects: [],
    exportBounds: [-200, -400, 800, 600],
  };
  assert.deepEqual(parseLevel3D(doc).exportBounds, [-200, -400, 800, 600]);
  for (const exportBounds of [
    [0, 0, 0, 10],
    [0, 0, 10, -1],
    [0, 0, 10.5, 20],
    [Infinity, 0, 10, 10],
  ])
    assert.throws(() => parseLevel3D({ ...doc, exportBounds }));
  assert.throws(() => parseSceneDoc({ ...doc, placements: [] }), /standalone/);
});
