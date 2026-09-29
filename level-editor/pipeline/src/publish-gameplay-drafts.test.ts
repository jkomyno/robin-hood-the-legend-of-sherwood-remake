import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { mergeGameplayDraft, publishGameplayDrafts } from "./publish-gameplay-drafts.ts";

test("draft merge preserves current artwork and rejects stale physical frames", () => {
  const { hut } = assetCompilerFixture();
  const live = structuredClone(hut);
  delete live.gameplay;
  live.model = "refined.glb";
  hut.gameplay!.draft = { issues: ["Provisional material"] };
  const merged = mergeGameplayDraft(live, hut, ["Masks pending"]);
  assert.equal(merged.model, "refined.glb");
  assert.deepEqual(merged.parts, live.parts);
  assert.ok(merged.gameplay!.draft!.issues.includes("Masks pending"));
  assert.ok(merged.gameplay!.draft!.issues.includes("Provisional material"));
  live.parts[0]!.name += " changed";
  assert.throws(() => mergeGameplayDraft(live, hut, []), /frames differ/);
});

test("draft merge does not replace independently authored gameplay", () => {
  const { hut } = assetCompilerFixture();
  const live = structuredClone(hut);
  live.gameplay!.doors = [];
  assert.throws(() => mergeGameplayDraft(live, hut, []), /reconciliation/);
});

test("publication backs up descriptors and repins both object and ground references", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gameplay-publish-"));
  try {
    const library = path.join(root, "library"),
      drafts = path.join(root, "drafts");
    const { hut } = assetCompilerFixture();
    const live = structuredClone(hut);
    delete live.gameplay;
    const encode = (value: unknown) => JSON.stringify(value) + "\n";
    const before = encode({ ...live, authoringNote: "retain" });
    const hash = createHash("sha256").update(before).digest("hex");
    const entry = {
      id: hut.id,
      name: hut.name,
      source_map: hut.source_map,
      descriptor: "hut/asset.json",
      model: `hut/${hut.model}`,
      descriptor_sha256: hash,
      editor: live,
    };
    const write = async (file: string, bytes: string) => {
      await fs.mkdir(path.dirname(file), { recursive: true });
      await fs.writeFile(file, bytes);
    };
    await write(path.join(library, "3d-assets/hut/asset.json"), before);
    await write(
      path.join(library, "3d-assets/index.json"),
      encode({ version: 1, assets: [entry] }),
    );
    const ref = { descriptor: "3d-assets/hut/asset.json", descriptor_sha256: hash };
    const scene = {
      assetSources: [ref],
      sceneAssets: [ref],
      placements: [{ id: "preserved", x: 42 }],
    };
    await write(path.join(library, "scenes/map.rhlos-map.json"), encode(scene));
    await write(
      path.join(drafts, "map/3d-assets/index.json"),
      encode({
        version: 1,
        assets: [
          {
            ...entry,
            editor: hut,
            descriptor_sha256: createHash("sha256").update(encode(hut)).digest("hex"),
          },
        ],
      }),
    );
    await write(path.join(drafts, "map/3d-assets/hut/asset.json"), encode(hut));
    await write(
      path.join(drafts, "map/gameplay-staging-report.json"),
      encode({ issues: [{ asset: hut.id, issues: ["Masks pending"] }] }),
    );
    const output = path.join(root, "backup");
    const report = await publishGameplayDrafts(library, drafts, output, true);
    assert.equal(report.applied, true);
    assert.deepEqual(report.published, [hut.id]);
    assert.equal(
      await fs.readFile(path.join(output, "before/3d-assets/hut/asset.json"), "utf8"),
      before,
    );
    const after = await fs.readFile(path.join(library, "3d-assets/hut/asset.json"), "utf8");
    assert.equal(JSON.parse(after).authoringNote, "retain");
    const updated = JSON.parse(
      await fs.readFile(path.join(library, "scenes/map.rhlos-map.json"), "utf8"),
    );
    assert.deepEqual(updated.placements, scene.placements);
    for (const item of [...updated.assetSources, ...updated.sceneAssets])
      assert.equal(item.descriptor_sha256, createHash("sha256").update(after).digest("hex"));
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
