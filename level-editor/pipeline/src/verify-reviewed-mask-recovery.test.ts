import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

test("a rejected source pin invalidates an earlier successful diagnostic batch", async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "mask-roundtrip-"));
  try {
    const source = path.join(directory, "source.json");
    const recipes = path.join(directory, "recipes.json");
    const manifest = path.join(directory, "diagnostics.json");
    await fs.writeFile(source, "{}");
    await fs.writeFile(recipes, JSON.stringify({ source_sha256: "0".repeat(64), recipes: [] }));
    await fs.writeFile(
      manifest,
      JSON.stringify({ complete: true, results: [{ file: "stale.level.json" }] }),
    );
    const result = spawnSync(
      process.execPath,
      [
        fileURLToPath(new URL("./verify-reviewed-mask-recovery.ts", import.meta.url)),
        "--library",
        directory,
        "--map",
        "unused",
        "--source",
        source,
        "--recovery",
        directory,
        "--mask-definitions",
        recipes,
        "--out",
        directory,
      ],
      { encoding: "utf8" },
    );
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Reviewed source changed/);
    const report = JSON.parse(await fs.readFile(manifest, "utf8"));
    assert.equal(report.complete, false);
    assert.deepEqual(report.results, []);
  } finally {
    await fs.rm(directory, { recursive: true, force: true });
  }
});
