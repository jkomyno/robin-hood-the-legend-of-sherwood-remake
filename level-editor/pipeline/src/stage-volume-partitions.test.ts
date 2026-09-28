import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { stageVolumePartitions } from "./stage-volume-partitions.ts";
import { readStoredMap, pinnedDescriptors } from "./stored-map.ts";
import { sha256 } from "./bundle-asset-states.ts";

async function fixture(root: string) {
  const library = path.join(root, "library"),
    draft = path.join(root, "draft"),
    out = path.join(root, "overlay");
  await fs.mkdir(path.join(library, "3d-assets/hut"), { recursive: true });
  await fs.mkdir(path.join(library, "scenes"));
  await fs.mkdir(draft);
  const { hut, document } = assetCompilerFixture();
  delete hut.gameplay;
  const bytes = JSON.stringify(hut),
    model = Buffer.from("model bytes unchanged by metadata staging");
  await fs.writeFile(path.join(library, "3d-assets/hut/asset.json"), bytes);
  await fs.writeFile(path.join(library, "3d-assets/hut/hut.glb"), model);
  await fs.writeFile(
    path.join(library, "3d-assets/index.json"),
    JSON.stringify({
      version: 1,
      assets: [{ id: hut.id, descriptor: "hut/asset.json", model: "hut/hut.glb", editor: hut }],
    }),
  );
  document.objects.splice(1);
  document.assetSources = [
    {
      id: hut.id,
      descriptor: "3d-assets/hut/asset.json",
      model: "3d-assets/hut/hut.glb",
      descriptor_sha256: sha256(bytes),
      model_sha256: sha256(model),
    },
  ];
  const map = path.join(library, "scenes/map.rhlos-map.json");
  await fs.writeFile(map, JSON.stringify(document));
  const corrected = structuredClone(hut);
  corrected.parts[0]!.obstacle_local_game!.points[0]!.x -= 1;
  const replacement = JSON.stringify(corrected);
  await fs.writeFile(path.join(draft, "asset.json"), replacement);
  const manifest = {
    parts: [{ asset: hut.id, descriptor_sha256: sha256(bytes), model_sha256: sha256(model) }],
    descriptors: [{ id: hut.id, path: "asset.json", sha256: sha256(replacement) }],
  };
  await fs.writeFile(path.join(draft, "partition-review.json"), JSON.stringify(manifest));
  return { library, draft, out, map, bytes, model, corrected, document, manifest };
}
test("partition overlays reopen corrected metadata without changing source files or model paths", async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "partition-overlay-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const f = await fixture(root);
  const result = await stageVolumePartitions(f);
  const saved = await readStoredMap(result.scene, result.library);
  assert.deepEqual(saved.objects[0]!.obstacle, f.corrected.parts[0]!.obstacle_local_game);
  assert.equal(saved.assetSources![0]!.model, "3d-assets/hut/hut.glb");
  assert.equal(
    await fs.readFile(path.join(f.library, "3d-assets/hut/asset.json"), "utf8"),
    f.bytes,
  );
  assert.deepEqual(await fs.readFile(path.join(f.out, "3d-assets/hut/hut.glb")), f.model);
  assert(!(await fs.lstat(path.join(f.out, "3d-assets/hut/asset.json"))).isSymbolicLink());
  const defs = await pinnedDescriptors(f.out, saved.assetSources!, saved.sceneAssets);
  assert.deepEqual(defs.get("hut")!.parts, f.corrected.parts);
  await assert.rejects(stageVolumePartitions(f), /EEXIST/);
});
test("scene-pinned assets absent from the palette become indexed in the draft overlay", async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "partition-overlay-index-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const f = await fixture(root);
  const indexPath = path.join(f.library, "3d-assets/index.json");
  await fs.writeFile(indexPath, JSON.stringify({ version: 1, assets: [] }));
  const result = await stageVolumePartitions(f);
  const index = JSON.parse(
    await fs.readFile(path.join(result.library, "3d-assets/index.json"), "utf8"),
  );
  assert.equal(index.assets.length, 1);
  assert.equal(index.assets[0].id, "hut");
  assert.equal(index.assets[0].model, "hut/hut.glb");
  assert.deepEqual(index.assets[0].editor.parts, f.corrected.parts);
  assert.deepEqual(JSON.parse(await fs.readFile(indexPath, "utf8")).assets, []);
});

test("partition staging rejects stale pins and explicit scene collision overrides", async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "partition-overlay-reject-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const f = await fixture(root);
  f.document.objects[0]!.obstacle!.points[0]!.x += 3;
  await fs.writeFile(f.map, JSON.stringify(f.document));
  await assert.rejects(stageVolumePartitions(f), /scene collision override/);
  f.manifest.parts[0]!.descriptor_sha256 = "0".repeat(64);
  await fs.writeFile(path.join(f.draft, "partition-review.json"), JSON.stringify(f.manifest));
  await assert.rejects(stageVolumePartitions(f), /pins changed/);
  await assert.rejects(fs.stat(f.out), /ENOENT/);
});
