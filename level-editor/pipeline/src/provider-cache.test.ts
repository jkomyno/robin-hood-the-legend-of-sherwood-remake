import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { cachedArtifacts, contentKey, inspectCache, validateGlb } from "./provider-cache.ts";

async function temp(t: { after(fn: () => Promise<void>): void }) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "pipeline-cache-test-"));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));
  return dir;
}
const validate = async (dir: string) => {
  const record = JSON.parse(await fs.readFile(path.join(dir, "response.json"), "utf8"));
  if (record.value !== 42) throw new Error("bad response");
  return record.value as number;
};
test("content keys frame boundaries and include all parameters", () => {
  assert.notEqual(contentKey(["ab", "c"]), contentKey(["a", "bc"]));
  assert.notEqual(contentKey(["endpoint1", "image"]), contentKey(["endpoint2", "image"]));
});
test("concurrent requests share one provider; complete cache is usable offline", async (t) => {
  const dir = path.join(await temp(t), "key");
  let calls = 0;
  const provider = async (staging: string) => {
    calls++;
    assert.equal((await inspectCache(dir, validate)).state, "miss");
    await fs.writeFile(path.join(staging, "response.json"), JSON.stringify({ value: 42 }));
  };
  assert.deepEqual(
    await Promise.all(Array.from({ length: 8 }, () => cachedArtifacts(dir, validate, provider))),
    Array(8).fill(42),
  );
  assert.equal(calls, 1);
  assert.equal(
    await cachedArtifacts(
      dir,
      validate,
      async () => {
        throw new Error("must not call provider");
      },
      { offline: true },
    ),
    42,
  );
  await fs.writeFile(path.join(dir, "response.json"), JSON.stringify({ value: 42, changed: true }));
  assert.equal((await inspectCache(dir, validate)).state, "corrupt");
  await assert.rejects(cachedArtifacts(dir, validate, provider), /corrupt/);
  assert.equal(calls, 1);
});
test("offline misses and interrupted downloads never become remote retries", async (t) => {
  const dir = path.join(await temp(t), "key");
  let calls = 0;
  const provider = async (staging: string) => {
    calls++;
    await fs.writeFile(path.join(staging, "response.json"), '{"value":42}');
    throw new Error("download failed after paid response");
  };
  await assert.rejects(
    cachedArtifacts(dir, validate, provider, { offline: true }),
    /offline.*miss/,
  );
  assert.equal(calls, 0);
  await assert.rejects(cachedArtifacts(dir, validate, provider), /download failed/);
  assert.equal((await inspectCache(dir, validate)).state, "corrupt");
  await assert.rejects(cachedArtifacts(dir, validate, provider), /corrupt/);
  assert.equal(calls, 1);
  assert.equal(JSON.parse(await fs.readFile(path.join(dir, "response.json"), "utf8")).value, 42);
});
test("invalid provider artifacts fail before atomic publication", async (t) => {
  const dir = path.join(await temp(t), "key");
  await assert.rejects(
    cachedArtifacts(dir, validate, async (staging) => {
      await fs.writeFile(path.join(staging, "response.json"), "not JSON");
    }),
  );
  await assert.rejects(fs.stat(path.join(dir, "complete.json")), {
    code: "ENOENT",
  });
});
function glb(): Buffer {
  let json = JSON.stringify({ asset: { version: "2.0" } });
  json += " ".repeat((4 - (json.length % 4)) % 4);
  const bytes = Buffer.alloc(20 + json.length);
  bytes.write("glTF");
  bytes.writeUInt32LE(2, 4);
  bytes.writeUInt32LE(bytes.length, 8);
  bytes.writeUInt32LE(json.length, 12);
  bytes.writeUInt32LE(0x4e4f534a, 16);
  bytes.write(json, 20);
  return bytes;
}
test("GLB validation rejects interrupted downloads", async (t) => {
  const file = path.join(await temp(t), "model.glb");
  await fs.writeFile(file, glb());
  await validateGlb(file);
  await fs.writeFile(file, glb().subarray(0, 25));
  await assert.rejects(validateGlb(file), /truncated/);
});
