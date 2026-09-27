/** One-time recovery across the library; the compiler never imports this tool. */
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { spawnSync } from "node:child_process";

const { values } = parseArgs({
  options: {
    library: { type: "string", default: "../library" },
    sources: { type: "string" },
    out: { type: "string" },
  },
});
if (!values.sources || !values.out)
  throw new Error(
    "Usage: --sources <authored-source-level-directory> --out <recovery-directory> [--library <library>]",
  );
const library = path.resolve(values.library),
  output = path.resolve(values.out);
const sources = new Map(
  (await fs.readdir(values.sources))
    .filter((n) => n.toLowerCase().endsWith(".rhp.json"))
    .map((name) => [name.slice(0, -9).toLowerCase(), path.resolve(values.sources!, name)]),
);
const results = [];
for (const file of (await fs.readdir(path.join(library, "scenes")))
  .filter((n) => n.endsWith(".rhlos-map.json"))
  .sort()) {
  const scenePath = path.join(library, "scenes", file);
  const scene = JSON.parse(await fs.readFile(scenePath, "utf8"));
  const sourceMap = typeof scene.sourceMap === "string" ? scene.sourceMap : undefined;
  if (!sourceMap) {
    results.push({
      file,
      status: "authored-scene",
      note: "No source-map recovery: use shared asset definitions and author scene-specific gameplay.",
    });
    continue;
  }
  const source = sources.get(sourceMap.toLowerCase());
  if (!source) {
    results.push({ file, status: "missing-source", sourceMap });
    continue;
  }
  const destination = path.join(output, sourceMap.toLowerCase());
  const run = spawnSync(
    process.execPath,
    [
      fileURLToPath(new URL("./recover-asset-gameplay.ts", import.meta.url)),
      "--map",
      scenePath,
      "--library",
      library,
      "--source",
      source,
      "--out",
      destination,
    ],
    { encoding: "utf8" },
  );
  if (run.status !== 0) {
    results.push({ file, status: "failed", error: run.error?.message ?? run.stderr });
    console.log(`FAIL ${file}: ${run.error?.message ?? run.stderr}`);
    continue;
  }
  const report = JSON.parse(
    await fs.readFile(path.join(destination, "recovery-report.json"), "utf8"),
  );
  results.push({
    file,
    status: "drafts-recovered",
    assets: report.assets,
    surfaces: report.surfaces,
    connections: report.connections,
    unresolved: report.unresolved.length,
    pending: report.pending,
  });
  console.log(
    `${file}: ${report.assets} asset drafts; ${report.unresolved.length} unresolved ownership/terrain records`,
  );
}
await fs.mkdir(output, { recursive: true });
await fs.writeFile(
  path.join(output, "library-recovery-report.json"),
  JSON.stringify({ version: 1, results }, null, 2) + "\n",
);
if (results.some((r) => ["failed", "missing-source"].includes(r.status))) process.exitCode = 1;
