/** Offline static geometry probes; these files are not publishable map exports. */
import fs from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import { readStoredMap, pinnedDescriptors } from "./stored-map.ts";
import { staticGameplaySnapshot } from "./diagnose-gameplay-candidates.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import type { GameplayAssetDescriptor } from "../../shared/src/asset-gameplay.ts";
import { normalizeGameplayStateViews } from "../../shared/src/gameplay-state-views.ts";

const { values } = parseArgs({
  options: {
    library: { type: "string", default: "../library" },
    recovery: { type: "string" },
    out: { type: "string" },
  },
});
if (!values.recovery || !values.out)
  throw new Error("Usage: --library <assets> --recovery <drafts> --out <diagnostics>");
await fs.mkdir(values.out, { recursive: true });
// Invalidate the previous batch before any recovery work can fail or be interrupted.
await fs.writeFile(
  path.join(values.out, "diagnostics.json"),
  JSON.stringify({
    scope: "static-geometry-only-not-gameplay-parity",
    results: [],
    complete: false,
  }) + "\n",
);
const results: { map: string; file?: string; error?: string; pending?: unknown }[] = [];
for (const map of (await fs.readdir(values.recovery, { withFileTypes: true }))
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)
  .sort()) {
  const result: (typeof results)[number] = { map };
  const file = `${map}.level.json`;
  await fs.rm(path.join(values.out, file), { force: true });
  try {
    const report = JSON.parse(
      await fs.readFile(path.join(values.recovery, map, "recovery-report.json"), "utf8"),
    );
    result.pending = report.pending;
    let document = staticGameplaySnapshot(
      await readStoredMap(
        path.join(values.library, "scenes", `${map}.rhlos-map.json`),
        values.library,
      ),
    );
    let assets = await pinnedDescriptors(
      values.library,
      document.assetSources ?? [],
      document.sceneAssets,
    );
    ({ document, descriptors: assets } = normalizeGameplayStateViews(document, assets));
    for (const [id, descriptor] of assets) {
      const packet = JSON.parse(
        await fs.readFile(path.join(values.recovery, map, `${id}.gameplay-authoring.json`), "utf8"),
      );
      if (!packet.gameplayCandidate) throw new Error(`Missing validated candidate for ${id}`);
      const candidate: GameplayAssetDescriptor = {
        ...descriptor,
        gameplay: packet.gameplayCandidate,
      };
      assets.set(id, candidate);
    }
    const bounds =
      document.exportBounds ??
      (document.size ? ([0, 0, ...document.size] as [number, number, number, number]) : undefined);
    if (!bounds) throw new Error("Map has no export bounds");
    const geometry = compileAssetGameplay(document, assets, bounds);
    const descriptor = {
      title: `Static diagnostic: ${map}`,
      map_filename: `diagnostic-${map}`,
      spawn_points: [],
      walkable_polygon: [
        [0, 0],
        [bounds[2] - 1, 0],
        [bounds[2] - 1, bounds[3] - 1],
        [0, bounds[3] - 1],
      ],
      volumes: [],
      asset_geometry: geometry,
    };
    await fs.writeFile(path.join(values.out, file), JSON.stringify(descriptor) + "\n");
    result.file = file;
  } catch (error) {
    result.error = String(error);
  }
  results.push(result);
  console.log(map, result.error ?? "static descriptor generated");
}
await fs.writeFile(
  path.join(values.out, "diagnostics.json"),
  JSON.stringify(
    {
      scope: "static-geometry-only-not-gameplay-parity",
      complete: results.length > 0 && results.every((result) => result.file && !result.error),
      results,
    },
    null,
    2,
  ) + "\n",
);
if (!results.length || results.some((result) => result.error)) process.exitCode = 1;
