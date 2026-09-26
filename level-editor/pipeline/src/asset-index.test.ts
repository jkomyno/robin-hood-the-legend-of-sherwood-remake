import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { writeAssetIndex } from "./asset-index.ts";

const sha = (bytes: Uint8Array | string) => createHash("sha256").update(bytes).digest("hex");

test("model publication copies validated derivatives and rejects stale unchanged assets before installation", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "asset-index-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const stage = join(root, "stage"),
    destination = join(root, "library");
  await mkdir(join(stage, "house"), { recursive: true });
  await mkdir(destination);
  const json = Buffer.from(JSON.stringify({ nodes: [{ name: "wall" }] }));
  const model = Buffer.alloc(20 + json.length);
  model.writeUInt32LE(json.length, 12);
  json.copy(model, 20);
  await writeFile(join(stage, "house/model.glb"), model);
  await writeFile(
    join(stage, "house/asset.json"),
    JSON.stringify({
      version: 1,
      id: "house",
      name: "House",
      parts: [{ node: "wall", obstacle_local_game: {} }],
    }),
  );
  await writeFile(join(stage, "house/lossy.glb"), "optimized");
  await writeFile(
    join(stage, "house/lossy.glb.receipt.json"),
    JSON.stringify({
      source: sha(model),
      output: sha("optimized"),
    }),
  );
  const entry = {
    id: "house",
    name: "House",
    source_map: "Derby",
    descriptor: "house/asset.json",
    model: "house/model.glb",
    lossy_model: "house/lossy.glb",
  };
  await writeFile(join(stage, "index.json"), JSON.stringify({ version: 1, assets: [entry] }));
  const publish = () =>
    execFileSync(
      process.execPath,
      [fileURLToPath(new URL("./publish-model-assets.ts", import.meta.url)), stage, destination],
      { stdio: ["pipe", "pipe", "pipe"] },
    );
  publish();
  assert.equal(await readFile(join(destination, "house/lossy.glb"), "utf8"), "optimized");
  assert.equal(
    await readFile(join(destination, "house/lossy.glb.receipt.json"), "utf8"),
    await readFile(join(stage, "house/lossy.glb.receipt.json"), "utf8"),
  );
  // A valid foreign asset is added, then its source is changed outside publication.
  await writeFile(join(destination, "foreign.glb"), "foreign original");
  await writeFile(join(destination, "foreign.lossy.glb"), "foreign optimized");
  await writeFile(
    join(destination, "foreign.lossy.glb.receipt.json"),
    JSON.stringify({
      source: sha("foreign original"),
      output: sha("foreign optimized"),
    }),
  );
  writeAssetIndex(destination, {
    version: 1,
    assets: [
      entry,
      {
        id: "foreign",
        model: "foreign.glb",
        lossy_model: "foreign.lossy.glb",
      },
    ],
  });
  const before = await readFile(join(destination, "index.json"));
  await writeFile(join(destination, "foreign.glb"), "changed");
  await writeFile(
    join(stage, "house/asset.json"),
    JSON.stringify({
      version: 1,
      id: "house",
      name: "House",
      parts: [{ node: "wall", obstacle_local_game: {} }],
      new_metadata: true,
    }),
  );
  const descriptor = await readFile(join(destination, "house/asset.json"));
  assert.throws(publish, /foreign: lossy receipt does not bind/);
  assert.deepEqual(await readFile(join(destination, "index.json")), before);
  assert.deepEqual(await readFile(join(destination, "house/asset.json")), descriptor);
});
