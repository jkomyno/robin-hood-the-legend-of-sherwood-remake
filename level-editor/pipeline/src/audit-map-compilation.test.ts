import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { createHash } from "node:crypto";
import { auditMapCompilation } from "./audit-map-compilation.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";

test("library audit compiles all maps, reports missing definitions and continues after failures", async () => {
  const library = await fs.mkdtemp(path.join(os.tmpdir(), "asset-compile-audit-"));
  try {
    await fs.mkdir(path.join(library, "scenes"));
    const { document, assets } = assetCompilerFixture();
    for (const reference of document.assetSources!) {
      const bytes = JSON.stringify(assets.get(reference.id));
      await fs.writeFile(path.join(library, reference.descriptor), bytes);
      reference.descriptor_sha256 = createHash("sha256").update(bytes).digest("hex");
    }
    await fs.writeFile(path.join(library, "scenes/valid.rhlos-map.json"), JSON.stringify(document));
    await fs.writeFile(path.join(library, "scenes/broken.rhlos-map.json"), "{}");
    const missing = structuredClone(document);
    const reference = missing.assetSources![0]!;
    const incomplete = structuredClone(assets.get(reference.id)!);
    delete incomplete.gameplay;
    const bytes = JSON.stringify(incomplete);
    reference.descriptor = "incomplete.json";
    reference.descriptor_sha256 = createHash("sha256").update(bytes).digest("hex");
    await fs.writeFile(path.join(library, reference.descriptor), bytes);
    await fs.writeFile(
      path.join(library, "scenes/missing.rhlos-map.json"),
      JSON.stringify(missing),
    );
    const report = await auditMapCompilation(library);
    assert.equal(report.maps, 3);
    assert.equal(report.ready, 1);
    assert.equal(report.results.find((r) => r.file.startsWith("valid"))!.ready, true);
    assert.deepEqual(report.results.find((r) => r.file.startsWith("missing"))!.missingGameplay, [
      "hut",
    ]);
    assert.ok(report.results.find((r) => r.file.startsWith("broken"))!.error);
    assert.equal(
      await fs.readFile(path.join(library, "scenes/valid.rhlos-map.json"), "utf8"),
      JSON.stringify(document),
    );
  } finally {
    await fs.rm(library, { recursive: true, force: true });
  }
});
