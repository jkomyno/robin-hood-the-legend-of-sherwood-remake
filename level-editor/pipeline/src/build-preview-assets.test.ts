import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { buildPreviews, previewTextureSize } from "./build-preview-assets.ts";
import { createHash } from "node:crypto";

async function fixture(t: { after: (fn: () => Promise<void>) => void }) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "preview-incremental-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  await fs.mkdir(path.join(root, "house"));
  await fs.writeFile(path.join(root, "house/model.glb"), "source1");
  await fs.writeFile(
    path.join(root, "index.json"),
    JSON.stringify({ version: 1, assets: [{ id: "house", model: "house/model.glb" }] }),
  );
  return root;
}

test("unchanged content skips generation and keeps output/index bytes and timestamps", async (t) => {
  const root = await fixture(t);
  let calls = 0;
  const options = {
    fingerprint: "settings1",
    generate: async () => {
      calls++;
      return Buffer.from("preview");
    },
  };
  assert.deepEqual(await buildPreviews(root, options), { generated: 1, skipped: 0 });
  const before = await fs.stat(path.join(root, "house/preview.glb"));
  const indexBefore = await fs.stat(path.join(root, "index.json"));
  assert.deepEqual(await buildPreviews(root, options), { generated: 0, skipped: 1 });
  assert.equal(calls, 1);
  assert.equal((await fs.stat(path.join(root, "house/preview.glb"))).mtimeMs, before.mtimeMs);
  assert.equal((await fs.stat(path.join(root, "index.json"))).mtimeMs, indexBefore.mtimeMs);
});

test("changed source bytes, settings, missing/corrupt output and receipt regenerate", async (t) => {
  const root = await fixture(t);
  let calls = 0;
  const options = {
    fingerprint: "settings1",
    generate: async () => Buffer.from(`preview${++calls}`),
  };
  await buildPreviews(root, options);
  const source = path.join(root, "house/model.glb"),
    stat = await fs.stat(source);
  await fs.writeFile(source, "source2");
  await fs.utimes(source, stat.atime, stat.mtime);
  await buildPreviews(root, options);
  options.fingerprint = "settings2";
  await buildPreviews(root, options);
  await fs.rm(path.join(root, "house/preview.glb"));
  await buildPreviews(root, options);
  await fs.writeFile(path.join(root, "house/preview.glb"), "corrupt");
  await buildPreviews(root, options);
  await fs.writeFile(path.join(root, "house/preview.glb.receipt.json"), "invalid json");
  await buildPreviews(root, options);
  assert.equal(calls, 6);
});

test("merges latest index without overwriting unrelated concurrent metadata or entries", async (t) => {
  const root = await fixture(t);
  const file = path.join(root, "index.json");
  await buildPreviews(root, {
    fingerprint: "a",
    generate: async () => {
      const latest = JSON.parse(await fs.readFile(file, "utf8"));
      latest.assets[0].label = "Updated label";
      latest.assets.push({ id: "other", model: "other/model.glb" });
      latest.extra = "preserve";
      await fs.writeFile(file, JSON.stringify(latest));
      return Buffer.from("preview");
    },
  });
  const result = JSON.parse(await fs.readFile(file, "utf8"));
  assert.equal(result.assets[0].label, "Updated label");
  assert.equal(result.assets[0].preview_model, "house/preview.glb");
  assert.equal(result.assets[1].id, "other");
  assert.equal(result.extra, "preserve");
});

test("changed source during generation rejects publication", async (t) => {
  const root = await fixture(t);
  await assert.rejects(
    buildPreviews(root, {
      fingerprint: "a",
      generate: async () => {
        await fs.writeFile(path.join(root, "house/model.glb"), "new source");
        return Buffer.from("stale preview");
      },
    }),
    /Asset changed/,
  );
  await assert.rejects(fs.stat(path.join(root, "house/preview.glb")), { code: "ENOENT" });
});

test("previews stay beside models in source-map folders", async (t) => {
  const root = await fixture(t);
  await fs.mkdir(path.join(root, "derby"));
  await fs.rename(path.join(root, "house"), path.join(root, "derby/house"));
  await fs.writeFile(
    path.join(root, "index.json"),
    JSON.stringify({ version: 1, assets: [{ id: "house", model: "derby/house/model.glb" }] }),
  );
  await buildPreviews(root, { fingerprint: "a", generate: async () => Buffer.from("preview") });
  const index = JSON.parse(await fs.readFile(path.join(root, "index.json"), "utf8"));
  assert.equal(index.assets[0].preview_model, "derby/house/preview.glb");
  assert.equal(await fs.readFile(path.join(root, "derby/house/preview.glb"), "utf8"), "preview");
});

test("failed generator preserves last published preview", async (t) => {
  const root = await fixture(t);
  await buildPreviews(root, { fingerprint: "a", generate: async () => Buffer.from("good") });
  await assert.rejects(
    buildPreviews(root, {
      fingerprint: "b",
      generate: async () => {
        throw new Error("encoder failed");
      },
    }),
    /encoder failed/,
  );
  assert.equal(await fs.readFile(path.join(root, "house/preview.glb"), "utf8"), "good");
});

test("CLI generates a real GLB once and then skips it", async (t) => {
  const { Document, NodeIO } = await import("@gltf-transform/core");
  const { execFile } = await import("node:child_process");
  const { promisify } = await import("node:util");
  const run = promisify(execFile);
  const root = await fixture(t);
  const doc = new Document();
  const buffer = doc.createBuffer();
  const positions = doc
    .createAccessor()
    .setType("VEC3")
    .setArray(new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]))
    .setBuffer(buffer);
  const indices = doc
    .createAccessor()
    .setType("SCALAR")
    .setArray(new Uint16Array([0, 1, 2]))
    .setBuffer(buffer);
  const primitive = doc.createPrimitive().setAttribute("POSITION", positions).setIndices(indices);
  doc.createScene().addChild(doc.createNode().setMesh(doc.createMesh().addPrimitive(primitive)));
  await new NodeIO().write(path.join(root, "house/model.glb"), doc);
  const script = new URL("./build-preview-assets.ts", import.meta.url);
  const first = await run(process.execPath, [script.pathname, root]);
  assert.match(first.stdout, /1 generated, 0 up to date/);
  const second = await run(process.execPath, [script.pathname, root]);
  assert.match(second.stdout, /0 generated, 1 up to date/);
  const bytes = await fs.readFile(path.join(root, "house/preview.glb"));
  assert.equal(bytes.toString("ascii", 0, 4), "glTF");
});

test("preview texture edge follows source texels: /8, multiple of 16, clamped 32-512", () => {
  assert.equal(previewTextureSize(112 * 112), 32);
  assert.equal(previewTextureSize(848 * 848), 112);
  assert.equal(previewTextureSize(3184 * 3184), 400);
  assert.equal(previewTextureSize(2944 * 2176), 320);
  assert.equal(previewTextureSize(8192 * 8192), 512);
  assert.throws(() => previewTextureSize(0), /no texture/);
});

test("current lossy models are the preview source; stale ones fall back to the model", async (t) => {
  const root = await fixture(t);
  const sha = (value: string) => createHash("sha256").update(value).digest("hex");
  const index = path.join(root, "index.json");
  await fs.writeFile(path.join(root, "house/lossy.glb"), "lossy1");
  await fs.writeFile(
    path.join(root, "house/lossy.glb.receipt.json"),
    JSON.stringify({ source: sha("source1"), output: sha("lossy1") }),
  );
  await fs.writeFile(
    index,
    JSON.stringify({
      version: 1,
      assets: [{ id: "house", model: "house/model.glb", lossy_model: "house/lossy.glb" }],
    }),
  );
  const sources: string[] = [];
  const options = {
    fingerprint: "a",
    generate: async (source: Uint8Array) => {
      sources.push(Buffer.from(source).toString());
      return Buffer.from("preview");
    },
  };
  await buildPreviews(root, options);
  const receipt = JSON.parse(
    await fs.readFile(path.join(root, "house/preview.glb.receipt.json"), "utf8"),
  );
  assert.deepEqual([receipt.source, receipt.source_model], [sha("lossy1"), "house/lossy.glb"]);
  await buildPreviews(root, options);
  assert.deepEqual(sources, ["lossy1"]);
  // Republished model without a rebuilt lossy model: preview the model itself.
  await fs.writeFile(path.join(root, "house/model.glb"), "source2");
  await buildPreviews(root, options);
  assert.deepEqual(sources, ["lossy1", "source2"]);
  // A lossy model that no longer matches its receipt is a broken library.
  await fs.writeFile(path.join(root, "house/lossy.glb"), "tampered");
  await assert.rejects(buildPreviews(root, options), /does not match its receipt/);
});
