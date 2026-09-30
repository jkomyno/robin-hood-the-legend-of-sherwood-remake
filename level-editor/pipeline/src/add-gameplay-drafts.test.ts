import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import {
  appendDraftPlacements,
  addGameplayDrafts,
  replaceDraftPlacements,
  verifyReplacementGeometry,
} from "./add-gameplay-drafts.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { serializeStoredMap } from "../../shared/src/stored-level.ts";
import { readStoredMap } from "./stored-map.ts";

test("family replacement removes obsolete placements and preserves unrelated authored content", () => {
  const kept = { id: "kept", assets: ["shared"], note: "retain" };
  const live = {
    camera: {},
    size: [10, 10],
    custom: true,
    placements: [kept, { id: "old", assets: ["obsolete", "shared"] }],
    assetSources: ["obsolete", "shared"].map((id) => ({
      id,
      descriptor: id,
      descriptor_sha256: "pin",
    })),
  };
  const staged = {
    ...live,
    placements: [kept, { id: "family", assets: ["new"] }],
    assetSources: [{ id: "new", descriptor: "new", descriptor_sha256: "pin" }],
  };
  const next = replaceDraftPlacements(live, staged, new Set(["new"]), new Set(["old"]));
  assert.deepEqual(next.placements, staged.placements);
  assert.deepEqual(
    next.assetSources.map((r) => r.id),
    ["shared", "new"],
  );
  assert.equal("custom" in next && next.custom, true);
  assert.equal(live.placements.length, 2);
  assert.throws(
    () => replaceDraftPlacements(live, staged, new Set(["new"]), new Set(["missing"])),
    /replacement placement/,
  );
});

test("family geometry proof rejects moved, missing and changed physical parts", () => {
  const { document } = assetCompilerFixture();
  const part = document.objects.find((o) => o.obstacle && o.source?.obstacle !== undefined)!;
  assert.ok(part);
  const live = structuredClone(document);
  live.objects = [structuredClone(part)];
  live.objects[0]!.group = undefined;
  const staged = structuredClone(live);
  staged.objects[0]!.id = "replacement";
  const removed = new Set([part.id]),
    added = new Set(["replacement"]);
  assert.equal(verifyReplacementGeometry(live, staged, removed, added), 1);
  staged.objects[0]!.obstacle!.points[0]!.x += 2;
  assert.throws(() => verifyReplacementGeometry(live, staged, removed, added), /world obstacle/);
  staged.objects = [];
  assert.throws(() => verifyReplacementGeometry(live, staged, removed, added), /part counts/);
});

test("additive placements preserve authored content and reject changed or mixed assemblies", () => {
  const existing = { id: "kept", assets: ["existing"], transform: { dx: 5 }, note: "user edit" };
  const fresh = { id: "light", assets: ["light"] };
  const live = {
    camera: {},
    size: [10, 10],
    placements: [existing],
    assetSources: [],
    custom: true,
  };
  const staged = {
    ...live,
    placements: [existing, fresh],
    assetSources: [{ id: "light", descriptor: "light/asset.json", descriptor_sha256: "pin" }],
  };
  const result = appendDraftPlacements(live, staged, new Set(["light"]));
  assert.deepEqual(result.placements[0], existing);
  assert.equal(live.placements.length, 1);
  assert.equal("custom" in result && result.custom, true);
  assert.throws(
    () =>
      appendDraftPlacements(
        live,
        { ...staged, placements: [{ ...existing, assets: ["moved"] }, fresh] },
        new Set(["light"]),
      ),
    /differs/,
  );
  assert.throws(
    () =>
      appendDraftPlacements(
        live,
        { ...staged, placements: [existing, { ...fresh, assets: ["light", "existing"] }] },
        new Set(["light"]),
      ),
    /reconciliation/,
  );
});

test("new asset publication copies resources, retains rollback bytes, repins and reopens the scene", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "add-gameplay-draft-"));
  try {
    const library = path.join(root, "library"),
      drafts = path.join(root, "drafts"),
      staged = path.join(drafts, "map");
    const { document, assets } = assetCompilerFixture();
    const json = (value: unknown) => JSON.stringify(value) + "\n";
    const sha = (bytes: string | Buffer) => createHash("sha256").update(bytes).digest("hex");
    const write = async (file: string, bytes: string | Buffer) => {
      await fs.mkdir(path.dirname(file), { recursive: true });
      await fs.writeFile(file, bytes);
    };
    const gltf = Buffer.from('{"asset":{"version":"2.0"}}  ');
    const model = Buffer.alloc(20 + gltf.length);
    model.writeUInt32LE(0x46546c67, 0);
    model.writeUInt32LE(2, 4);
    model.writeUInt32LE(model.length, 8);
    model.writeUInt32LE(gltf.length, 12);
    model.writeUInt32LE(0x4e4f534a, 16);
    gltf.copy(model, 20);
    const entries = [];
    for (const ref of document.assetSources ?? []) {
      const descriptor = assets.get(ref.id)!;
      descriptor.model = "model.glb";
      const bytes = json(descriptor);
      ref.descriptor = `3d-assets/${ref.id}/asset.json`;
      ref.descriptor_sha256 = sha(bytes);
      ref.model = `3d-assets/${ref.id}/model.glb`;
      ref.model_sha256 = sha(model);
      await write(path.join(staged, ref.descriptor), bytes);
      await write(path.join(staged, ref.model), model);
      entries.push({
        id: descriptor.id,
        name: descriptor.name,
        source_map: descriptor.source_map,
        descriptor: `${ref.id}/asset.json`,
        descriptor_sha256: ref.descriptor_sha256,
        model: `${ref.id}/model.glb`,
        model_sha256: ref.model_sha256,
        editor: descriptor,
      });
    }
    document.map = "map";
    const stored = serializeStoredMap(document, assets);
    assert.ok(stored && typeof stored === "object" && !Array.isArray(stored));
    const before = json({ ...stored, placements: [], assetSources: [] });
    await write(path.join(staged, "scenes/map.rhlos-map.json"), json(stored));
    await write(path.join(staged, "3d-assets/index.json"), json({ version: 1, assets: entries }));
    await write(
      path.join(staged, "gameplay-staging-report.json"),
      json({ issues: [{ asset: entries[0]!.id, issues: ["Masks pending"] }] }),
    );
    await write(path.join(library, "3d-assets/index.json"), json({ version: 1, assets: [] }));
    await write(path.join(library, "scenes/map.rhlos-map.json"), before);
    const selection = [{ map: "map", assets: entries.map((e) => e.id) }];
    const modelPath = path.join(staged, "3d-assets", entries[0]!.model);
    await fs.writeFile(modelPath, Buffer.from("corrupt"));
    await assert.rejects(
      addGameplayDrafts(library, drafts, selection, path.join(root, "rejected"), true),
      /Stale draft model/,
    );
    assert.equal(
      await fs.readFile(path.join(library, "scenes/map.rhlos-map.json"), "utf8"),
      before,
    );
    await assert.rejects(fs.stat(path.join(library, "3d-assets", entries[0]!.descriptor)), {
      code: "ENOENT",
    });
    await fs.writeFile(modelPath, model);
    const backup = path.join(root, "backup");
    const report = await addGameplayDrafts(library, drafts, selection, backup, true);
    assert.equal(report.applied, true);
    assert.equal(
      await fs.readFile(path.join(backup, "before/scenes/map.rhlos-map.json"), "utf8"),
      before,
    );
    const reopened = await readStoredMap(path.join(library, "scenes/map.rhlos-map.json"), library);
    assert.equal(reopened.objects.length, document.objects.length);
    for (const entry of entries)
      assert.equal(
        (await fs.lstat(path.join(library, "3d-assets", entry.model))).isSymbolicLink(),
        false,
      );
    await assert.rejects(
      addGameplayDrafts(library, drafts, selection, path.join(root, "repeat"), true),
      /reconciliation|conflicting|Existing/,
    );
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
