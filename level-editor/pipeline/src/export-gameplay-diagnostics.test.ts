import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

test("failed diagnostic batches invalidate stale files and fail the command", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "map-diagnostics-"));
  try {
    const recovery = path.join(root, "recovery");
    const out = path.join(root, "out");
    await fs.mkdir(out);
    await fs.mkdir(recovery);
    const run = () =>
      spawnSync(
        process.execPath,
        [
          "--max-old-space-size=512",
          fileURLToPath(new URL("./export-gameplay-diagnostics.ts", import.meta.url)),
          "--library",
          path.join(root, "library"),
          "--recovery",
          recovery,
          "--out",
          out,
        ],
        { encoding: "utf8" },
      );
    for (const map of ["derby", "york"]) {
      await fs.mkdir(path.join(recovery, map));
      await fs.writeFile(path.join(out, `${map}.level.json`), "stale output");
    }
    await fs.writeFile(path.join(out, "diagnostics.json"), '{"complete":true}');
    const failed = run();
    assert.equal(failed.status, 1, failed.stderr);
    const manifest = JSON.parse(await fs.readFile(path.join(out, "diagnostics.json"), "utf8"));
    assert.equal(manifest.complete, false);
    assert.deepEqual(
      manifest.results.map((result: { map: string }) => result.map),
      ["derby", "york"],
    );
    for (const result of manifest.results) {
      assert.match(result.error, /recovery-report.json/);
      assert.equal(result.file, undefined);
      await assert.rejects(fs.stat(path.join(out, `${result.map}.level.json`)), { code: "ENOENT" });
    }
    await fs.rm(recovery, { recursive: true });
    await fs.mkdir(recovery);
    assert.equal(run().status, 1, "an empty batch cannot pass");
    const empty = JSON.parse(await fs.readFile(path.join(out, "diagnostics.json"), "utf8"));
    assert.equal(empty.complete, false);
    assert.deepEqual(empty.results, []);
    await fs.rm(recovery, { recursive: true });
    await fs.writeFile(path.join(out, "diagnostics.json"), '{"complete":true}');
    assert.equal(run().status, 1, "a missing recovery directory cannot pass");
    const interrupted = JSON.parse(await fs.readFile(path.join(out, "diagnostics.json"), "utf8"));
    assert.equal(interrupted.complete, false, "previous manifest was invalidated before discovery");
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
