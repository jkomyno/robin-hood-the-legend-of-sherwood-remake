/** Offline static mask checks. Successful diagnostics are not publishable maps. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { parseArgs } from "node:util";
import type { ProtoLevel } from "../../shared/src/level.ts";
import type { AssetGameplay, GameplayAssetDescriptor } from "../../shared/src/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { normalizeGameplayStateViews } from "../../shared/src/gameplay-state-views.ts";
import { readStoredMap, pinnedDescriptors } from "./stored-map.ts";
import { staticGameplaySnapshot } from "./diagnose-gameplay-candidates.ts";
import type { ReviewedMaskRecipe } from "./recover-reviewed-masks.ts";
import { maskCoverage, matchRecoveredMasks, verifyMaskTranslation } from "./mask-roundtrip.ts";

const { values } = parseArgs({
  options: {
    library: { type: "string" },
    map: { type: "string" },
    source: { type: "string" },
    recovery: { type: "string" },
    "mask-definitions": { type: "string" },
    out: { type: "string" },
    "move-x": { type: "string", default: "1" },
  },
});
if (
  !values.library ||
  !values.map ||
  !values.source ||
  !values.recovery ||
  !values["mask-definitions"] ||
  !values.out
)
  throw new Error(
    "Usage: --library <assets> --map <scene> --source <level> --recovery <drafts> --mask-definitions <recipes> --out <diagnostics> [--move-x <integer>]",
  );
const dx = Number(values["move-x"]);
assert.ok(Number.isSafeInteger(dx) && dx !== 0, "Movement must be a nonzero integer");
await fs.mkdir(values.out, { recursive: true });
const manifest = {
  scope: "static-geometry-only-not-gameplay-parity",
  complete: false,
  movement: { dx },
  results: [] as { map: string; file: string }[],
  masks: [] as { asset: string; source: number; compiled: number[]; pixels: number }[],
  movementFailures: [] as { asset: string; error: string }[],
};
const manifestPath = path.join(values.out, "diagnostics.json");
const save = () => fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
// Never leave an earlier successful manifest visible after an interrupted rerun.
await save();
const bytes = await fs.readFile(values.source);
const source: ProtoLevel = JSON.parse(bytes.toString("utf8"));
const reviewed: { source_sha256: string; recipes: ReviewedMaskRecipe[] } = JSON.parse(
  await fs.readFile(values["mask-definitions"], "utf8"),
);
assert.equal(
  createHash("sha256").update(bytes).digest("hex"),
  reviewed.source_sha256,
  "Reviewed source changed",
);
assert.ok(reviewed.recipes.length, "No reviewed mask recipes");
let document = staticGameplaySnapshot(await readStoredMap(values.map, values.library));
let assets = await pinnedDescriptors(
  values.library,
  document.assetSources ?? [],
  document.sceneAssets,
);
({ document, descriptors: assets } = normalizeGameplayStateViews(document, assets));
for (const [id, descriptor] of assets) {
  const packet: { asset: string; gameplayCandidate?: AssetGameplay } = JSON.parse(
    await fs.readFile(path.join(values.recovery, `${id}.gameplay-authoring.json`), "utf8"),
  );
  assert.equal(packet.asset, id, "Recovery packet belongs to a different asset");
  assert.ok(packet.gameplayCandidate, `Missing candidate for ${id}`);
  const candidate: GameplayAssetDescriptor = { ...descriptor, gameplay: packet.gameplayCandidate };
  assets.set(id, candidate);
}
const bounds =
  document.exportBounds ??
  (document.size ? ([0, 0, ...document.size] as [number, number, number, number]) : undefined);
assert.ok(bounds, "Missing export bounds");
const baseline = compileAssetGameplay(document, assets, bounds);
const write = async (map: string, geometry: typeof baseline) => {
  const file = `case-${manifest.results.length}.level.json`;
  await fs.writeFile(
    path.join(values.out!, file),
    JSON.stringify({
      title: `Static mask diagnostic: ${map}`,
      map_filename: `diagnostic-${path.basename(values.map!, ".rhlos-map.json")}`,
      spawn_player: false,
      walkable_polygon: [
        [0, 0],
        [bounds[2] - 1, 0],
        [bounds[2] - 1, bounds[3] - 1],
        [0, bounds[3] - 1],
      ],
      volumes: [],
      asset_geometry: geometry,
    }) + "\n",
  );
  manifest.results.push({ map, file });
};
await write("baseline", baseline);
const used = new Set<number>();
const sourceIndices = new Set<number>();
for (const recipe of reviewed.recipes) {
  assert.equal(
    document.assetSources?.find((a) => a.id === recipe.asset)?.model_sha256,
    recipe.model_sha256,
    `Reviewed model changed: ${recipe.asset}`,
  );
  assert.ok(recipe.entries.length, `Empty recipe: ${recipe.asset}`);
  const indices = recipe.entries.flatMap((entry) => {
    assert.ok(!sourceIndices.has(entry.source), "Repeated source mask");
    sourceIndices.add(entry.source);
    const expected = source.masks[entry.source];
    assert.ok(expected, `Missing source mask ${entry.source}`);
    const indices = matchRecoveredMasks(expected, baseline.masks ?? []);
    for (const index of indices) {
      assert.ok(!used.has(index), "Source masks cannot share one compiled record");
      used.add(index);
    }
    manifest.masks.push({
      asset: recipe.asset,
      source: entry.source,
      compiled: indices,
      pixels: maskCoverage(expected).size,
    });
    return indices;
  });
  const movedDocument = structuredClone(document);
  const parts = movedDocument.objects.filter((p) => p.node.startsWith(`asset:${recipe.asset}:`));
  assert.equal(
    new Set(parts.map((p) => p.node)).size,
    parts.length,
    "Verification needs one placement per asset",
  );
  const groups = new Set(parts.map((p) => p.group));
  assert.equal(groups.size, 1, "Asset parts must share a placement group");
  const group = movedDocument.groups.find((g) => g.id === [...groups][0]);
  assert.ok(group, `Missing placement for ${recipe.asset}`);
  group.transform.dx += dx;
  try {
    const moved = compileAssetGameplay(movedDocument, assets, bounds);
    for (const index of indices) {
      const mask = moved.masks?.[index];
      assert.ok(mask, "Moved mask disappeared");
      verifyMaskTranslation(baseline.masks![index]!, mask, dx);
    }
    await write(recipe.asset, moved);
    console.log(
      `${recipe.asset}: ${recipe.entries.length} source masks (${indices.length} compiled tiles) verified at baseline and dx=${dx}`,
    );
  } catch (error) {
    manifest.movementFailures.push({ asset: recipe.asset, error: String(error) });
  }
  await save();
}
assert.equal(
  used.size,
  baseline.masks?.length ?? 0,
  "Compiled masks not covered by reviewed recipes",
);
manifest.complete = manifest.movementFailures.length === 0;
await save();
assert.ok(
  manifest.complete,
  `Mask placement checks failed: ${JSON.stringify(manifest.movementFailures)}`,
);
