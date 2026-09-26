import test from "node:test";
import assert from "node:assert/strict";
import { SpriteAtlasImages, spriteAtlasRect } from "./sprite-atlas.ts";

test("atlas frames validate dimensions and reject rectangles outside the image", () => {
  assert.deepEqual(spriteAtlasRect([4, 5, 20, 30], 24, 35), [4, 5, 20, 30]);
  for (const value of [
    undefined,
    [0, 0, 0, 1],
    [-1, 0, 1, 1],
    [0, 0, 25, 1],
    [0, 34, 1, 2],
    [0.5, 0, 1, 1],
  ])
    assert.throws(() => spriteAtlasRect(value, 24, 35), /atlas rectangle/);
});

test("mission atlas cache fetches and decodes once across poses, then releases the bitmap", async (t) => {
  let reads = 0,
    decodes = 0,
    closes = 0;
  const original = globalThis.createImageBitmap;
  globalThis.createImageBitmap = (async () => {
    decodes++;
    return { close: () => closes++ } as unknown as ImageBitmap;
  }) as typeof createImageBitmap;
  t.after(() => {
    globalThis.createImageBitmap = original;
  });
  const directory = {
    async getFileHandle() {
      reads++;
      return { getFile: async () => new Blob() };
    },
  } as unknown as FileSystemDirectoryHandle;
  const images = new SpriteAtlasImages();
  const a = images.get(directory, "guard", "atlas.png");
  const b = images.get(directory, "guard", "atlas.png");
  assert.equal(await a, await b);
  assert.equal(reads, 1);
  assert.equal(decodes, 1);
  assert.throws(() => images.get(directory, "guard", "../atlas.png"), /Invalid sprite atlas path/);
  images.dispose();
  await Promise.resolve();
  assert.equal(closes, 1);
  images.dispose();
  await Promise.resolve();
  assert.equal(closes, 1);
});
