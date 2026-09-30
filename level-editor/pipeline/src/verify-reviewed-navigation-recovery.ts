/** Offline placement diagnostics; successful construction is not full map parity. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { parseArgs } from "node:util";
import { readStoredMap, pinnedDescriptors } from "./stored-map.ts";
import { staticGameplaySnapshot } from "./diagnose-gameplay-candidates.ts";
import { normalizeGameplayStateViews } from "../../shared/src/gameplay-state-views.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import type { AssetGameplay, GameplayAssetDescriptor } from "../../shared/src/asset-gameplay.ts";
import type { ProtoLevel } from "../../shared/src/level.ts";
import type { RecoveredGameplayPacket } from "./recovered-gameplay-definition.ts";
import {
  recoverReviewedNavigationJoins,
  type ReviewedNavigationJoins,
} from "./recover-reviewed-navigation-joins.ts";

const { values } = parseArgs({
  options: {
    library: { type: "string" },
    map: { type: "string" },
    source: { type: "string" },
    recovery: { type: "string" },
    "navigation-definitions": { type: "string" },
    out: { type: "string" },
    "move-x": { type: "string", default: "1" },
  },
});
if (
  !values.library ||
  !values.map ||
  !values.source ||
  !values.recovery ||
  !values["navigation-definitions"] ||
  !values.out
)
  throw new Error(
    "Usage: --library <assets> --map <scene> --source <level> --recovery <packets> --navigation-definitions <recipes> --out <diagnostics> [--move-x <integer>]",
  );
const dx = Number(values["move-x"]);
assert.ok(Number.isSafeInteger(dx) && dx !== 0, "Movement must be a nonzero integer");
await fs.mkdir(values.out, { recursive: true });
const manifest = {
  scope: "static-geometry-only-not-gameplay-parity",
  complete: false,
  movement: { dx },
  results: [] as { map: string; file: string }[],
  movementFailures: [] as { asset: string; error: string }[],
};
const save = () =>
  fs.writeFile(
    path.join(values.out!, "diagnostics.json"),
    JSON.stringify(manifest, null, 2) + "\n",
  );
await save();
const bytes = await fs.readFile(values.source),
  source: ProtoLevel = JSON.parse(bytes.toString());
const definitions: ReviewedNavigationJoins = JSON.parse(
  await fs.readFile(values["navigation-definitions"], "utf8"),
);
let document = staticGameplaySnapshot(await readStoredMap(values.map, values.library));
let descriptors = await pinnedDescriptors(
  values.library,
  document.assetSources ?? [],
  document.sceneAssets,
);
({ document, descriptors } = normalizeGameplayStateViews(document, descriptors));
const packets = new Map<string, RecoveredGameplayPacket>();
const candidates = new Map<string, GameplayAssetDescriptor>();
for (const [asset, descriptor] of descriptors) {
  const packet: RecoveredGameplayPacket & { gameplayCandidate?: AssetGameplay } = JSON.parse(
    await fs.readFile(path.join(values.recovery, `${asset}.gameplay-authoring.json`), "utf8"),
  );
  assert.equal(packet.asset, asset, "Recovery packet belongs to another asset");
  assert.ok(packet.gameplayCandidate, `Missing candidate for ${asset}`);
  packets.set(asset, packet);
  const candidate: GameplayAssetDescriptor = { ...descriptor, gameplay: packet.gameplayCandidate };
  candidates.set(asset, candidate);
}
for (const region of definitions.regions)
  for (const entry of region.entries) {
    const packet = packets.get(entry.asset);
    assert.ok(packet, `Missing packet for ${entry.asset}`);
    for (const surface of [
      packet.surfaces.find((s) => s.id === entry.surface),
      candidates.get(entry.asset)?.gameplay?.surfaces.find((s) => s.id === entry.surface),
    ]) {
      assert.ok(surface, `Missing surface ${entry.asset}/${entry.surface}`);
      assert.equal(
        surface.navigationRegion,
        region.id,
        "Recovered region differs from reviewed definition",
      );
      assert.deepEqual(
        surface.navigationJoins,
        entry.edges,
        "Recovered joins differ from reviewed definition",
      );
    }
    // Revalidate the authoring inputs without reinserting already recovered joins.
    delete packet.surfaces.find((s) => s.id === entry.surface)!.navigationJoins;
  }
recoverReviewedNavigationJoins(
  document,
  source,
  createHash("sha256").update(bytes).digest("hex"),
  definitions,
  packets,
);
const bounds =
  document.exportBounds ??
  (document.size ? ([0, 0, ...document.size] as [number, number, number, number]) : undefined);
assert.ok(bounds, "Missing export bounds");
const write = async (map: string, geometry: ReturnType<typeof compileAssetGameplay>) => {
  const file = `case-${manifest.results.length}.level.json`;
  await fs.writeFile(
    path.join(values.out!, file),
    JSON.stringify({
      title: `Static navigation diagnostic: ${map}`,
      map_filename: `diagnostic-${path.basename(values.map!, ".rhlos-map.json")}`,
      spawn_points: [],
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
  await save();
};
const baseline = compileAssetGameplay(document, candidates, bounds);
assert.ok(
  !(baseline.warnings ?? []).some((w) => w.includes("no matching boundary edge")),
  "Reviewed baseline has detached navigation joins",
);
await write("baseline", baseline);
for (const asset of new Set(definitions.regions.flatMap((r) => r.entries.map((e) => e.asset)))) {
  try {
    const moved = structuredClone(document),
      parts = moved.objects.filter((p) => p.node.startsWith(`asset:${asset}:`));
    const groups = new Set(parts.map((p) => p.group));
    assert.equal(groups.size, 1, `Expected one placed group for ${asset}`);
    const group = moved.groups.find((g) => g.id === [...groups][0]);
    assert.ok(group, `Missing placement group for ${asset}`);
    group.transform.dx += dx;
    const geometry = compileAssetGameplay(moved, candidates, bounds);
    assert.ok(
      (geometry.warnings ?? []).some(
        (w) => w.includes("no matching boundary edge") && w.includes(asset),
      ),
      `Moved join did not detach for ${asset}`,
    );
    await write(asset, geometry);
    console.log(`${asset}: recovered joins compile at baseline and dx=${dx}`);
  } catch (error) {
    manifest.movementFailures.push({ asset, error: String(error) });
    await save();
  }
}
manifest.complete = manifest.movementFailures.length === 0;
await save();
assert.ok(
  manifest.complete,
  `Navigation placement checks failed: ${JSON.stringify(manifest.movementFailures)}`,
);
