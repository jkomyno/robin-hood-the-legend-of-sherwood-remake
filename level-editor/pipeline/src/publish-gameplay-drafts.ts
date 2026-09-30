import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { pathToFileURL } from "node:url";
import {
  parseProjectionAssetDescriptor,
  parseProjectionAssetIndex,
} from "../../shared/src/validation.ts";
import type { GameplayAssetDescriptor as ProjectionAssetDescriptor } from "../../shared/src/asset-gameplay.ts";
import {
  reconcilePhysicalDraft,
  REVIEWED_PHYSICAL_FIELDS,
  verifyPhysicalModelFrames,
  verifyPhysicalPartIdentity,
} from "./reconcile-physical-drafts.ts";

/** Merge definitions only when the current asset still has the recovered local frames. */
export function mergeGameplayDraft(
  live: ProjectionAssetDescriptor,
  draft: ProjectionAssetDescriptor,
  issues: string[],
): ProjectionAssetDescriptor {
  if (
    live.id !== draft.id ||
    !isDeepStrictEqual(live.parts, draft.parts) ||
    !isDeepStrictEqual(live.source_origin_scene, draft.source_origin_scene)
  )
    throw new Error(`${live.id}: recovered part frames differ from the current asset`);
  if (!draft.gameplay) throw new Error(`${live.id}: no recovered gameplay`);
  if (live.gameplay && !isDeepStrictEqual(live.gameplay, draft.gameplay))
    throw new Error(`${live.id}: current gameplay requires explicit reconciliation`);
  return parseProjectionAssetDescriptor({
    ...live,
    gameplay: {
      ...draft.gameplay,
      draft: {
        issues: [
          ...new Set([
            "Incomplete gameplay recovery; full parity is not certified.",
            ...(draft.gameplay.draft?.issues ?? []),
            ...issues,
          ]),
        ],
      },
    },
  });
}

const sha = (bytes: string | Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const encode = (value: unknown) => JSON.stringify(value) + "\n";
type Change = { file: string; before: string; after: string };

/** Publish metadata and repin saved scenes together, retaining exact rollback bytes. */
export async function publishGameplayDrafts(
  library: string,
  drafts: string,
  output: string,
  apply: boolean,
  reviewedPhysicalAssets?: ReadonlySet<string>,
) {
  library = path.resolve(library);
  output = path.resolve(output);
  if (output === library || output.startsWith(library + path.sep))
    throw new Error("Publication backup must be outside the library");
  await fs.mkdir(output, { recursive: false });
  const indexFile = "3d-assets/index.json";
  const indexBefore = await fs.readFile(path.join(library, indexFile), "utf8");
  const index = parseProjectionAssetIndex(JSON.parse(indexBefore));
  const recovered = new Map<
    string,
    {
      descriptor: ProjectionAssetDescriptor;
      issues: string[];
      model: string;
      modelSha: string | undefined;
      rawParts: Record<string, unknown>[];
    }
  >();
  for (const directory of await fs.readdir(drafts, { withFileTypes: true })) {
    if (!directory.isDirectory()) continue;
    const root = path.join(drafts, directory.name);
    const report = JSON.parse(
      await fs.readFile(path.join(root, "gameplay-staging-report.json"), "utf8"),
    ) as {
      issues: { asset: string; issues: string[] }[];
    };
    const catalog = parseProjectionAssetIndex(
      JSON.parse(await fs.readFile(path.join(root, indexFile), "utf8")),
    );
    for (const entry of catalog) {
      if (reviewedPhysicalAssets && !reviewedPhysicalAssets.has(entry.id)) continue;
      const bytes = await fs.readFile(path.join(root, "3d-assets", entry.descriptor), "utf8");
      if (sha(bytes) !== entry.descriptor_sha256)
        throw new Error(`Stale recovered catalog: ${entry.id}`);
      const descriptor = parseProjectionAssetDescriptor(JSON.parse(bytes));
      if (recovered.has(descriptor.id))
        throw new Error(`Duplicate recovered asset ${descriptor.id}`);
      recovered.set(descriptor.id, {
        descriptor,
        rawParts: JSON.parse(bytes).parts,
        model: path.join(root, "3d-assets", entry.model),
        modelSha: entry.model_sha256,
        issues: report.issues.find((item) => item.asset === descriptor.id)?.issues ?? [],
      });
    }
  }
  const changes: Change[] = [];
  const published: string[] = [];
  const skipped: { asset: string; reason: string }[] = [];
  const pins = new Map<string, { before: string; after: string }>();
  const physicalReviews: {
    asset: string;
    verifiedPartFrames: number;
    modelSha256: string;
    draftModelSha256: string;
  }[] = [];
  const reviewedModels = new Map<string, { model: string; sha: string; sceneVerified: boolean }>();
  for (const entry of index) {
    if (reviewedPhysicalAssets && !reviewedPhysicalAssets.has(entry.id)) continue;
    const candidate = recovered.get(entry.id);
    if (!candidate) {
      if (reviewedPhysicalAssets) throw new Error(`Missing reviewed physical draft: ${entry.id}`);
      skipped.push({ asset: entry.id, reason: "No recovered draft for this asset identity" });
      continue;
    }
    const file = "3d-assets/" + entry.descriptor;
    const before = await fs.readFile(path.join(library, file), "utf8");
    if (sha(before) !== entry.descriptor_sha256) throw new Error(`Stale catalog: ${entry.id}`);
    const live = parseProjectionAssetDescriptor(JSON.parse(before));
    let merged: ProjectionAssetDescriptor;
    try {
      if (reviewedPhysicalAssets) {
        verifyPhysicalPartIdentity(JSON.parse(before).parts, candidate.rawParts);
        const liveModel = await fs.readFile(path.join(library, "3d-assets", entry.model));
        const draftModel = await fs.readFile(candidate.model);
        const liveSha = sha(liveModel);
        if (
          !candidate.modelSha ||
          (entry.model_sha256 && liveSha !== entry.model_sha256) ||
          sha(draftModel) !== candidate.modelSha
        )
          throw new Error(`Stale reviewed model: ${entry.id}`);
        const verifiedPartFrames = verifyPhysicalModelFrames(
          liveModel,
          live,
          draftModel,
          candidate.descriptor,
        );
        merged = reconcilePhysicalDraft(live, candidate.descriptor, candidate.issues);
        physicalReviews.push({
          asset: entry.id,
          verifiedPartFrames,
          modelSha256: liveSha,
          draftModelSha256: candidate.modelSha,
        });
        reviewedModels.set(file, {
          model: "3d-assets/" + entry.model,
          sha: liveSha,
          sceneVerified: false,
        });
      } else merged = mergeGameplayDraft(live, candidate.descriptor, candidate.issues);
    } catch (error) {
      if (reviewedPhysicalAssets) throw error;
      skipped.push({ asset: entry.id, reason: String(error) });
      continue;
    }
    // Preserve authoring fields outside the runtime descriptor schema.
    const raw = JSON.parse(before);
    const after = encode({
      ...raw,
      ...(reviewedPhysicalAssets
        ? {
            parts: (raw.parts as Record<string, unknown>[]).map((part, i) =>
              Object.fromEntries([
                ...Object.entries(part).filter(([key]) => !REVIEWED_PHYSICAL_FIELDS.has(key)),
                ...Object.entries(merged.parts[i]!).filter(([key]) =>
                  REVIEWED_PHYSICAL_FIELDS.has(key),
                ),
              ]),
            ),
          }
        : {}),
      gameplay: merged.gameplay,
    });
    changes.push({ file, before, after });
    pins.set(file, { before: sha(before), after: sha(after) });
    entry.editor = merged;
    entry.descriptor_sha256 = sha(after);
    published.push(entry.id);
  }
  if (reviewedPhysicalAssets && published.length !== reviewedPhysicalAssets.size)
    throw new Error("Missing reviewed physical asset identities in current library");
  const scenes: string[] = [];
  for (const name of await fs.readdir(path.join(library, "scenes"))) {
    if (!name.endsWith(".rhlos-map.json")) continue;
    const file = "scenes/" + name;
    const before = await fs.readFile(path.join(library, file), "utf8");
    const document = JSON.parse(before) as {
      assetSources?: {
        descriptor: string;
        descriptor_sha256: string;
        model?: string;
        model_sha256?: string;
      }[];
      sceneAssets?: {
        descriptor?: string;
        descriptor_sha256?: string;
        model?: string;
        model_sha256?: string;
      }[];
    };
    let changed = false;
    for (const ref of [...(document.assetSources ?? []), ...(document.sceneAssets ?? [])]) {
      const pin = ref.descriptor && pins.get(ref.descriptor);
      if (!pin) continue;
      if (ref.descriptor_sha256 !== pin.before)
        throw new Error(`${file}: stale saved descriptor ${ref.descriptor}`);
      const model = reviewedModels.get(ref.descriptor!);
      if (model) {
        if (ref.model !== model.model || ref.model_sha256 !== model.sha)
          throw new Error(`${file}: stale saved model for physical review ${ref.descriptor}`);
        model.sceneVerified = true;
      }
      ref.descriptor_sha256 = pin.after;
      changed = true;
    }
    if (changed) {
      changes.push({ file, before, after: JSON.stringify(document, null, 2) + "\n" });
      scenes.push(name);
    }
  }
  for (const [descriptor, model] of reviewedModels)
    if (!model.sceneVerified)
      throw new Error(`Missing pinned scene model for physical review: ${descriptor}`);
  parseProjectionAssetIndex({ version: 1, assets: index });
  changes.push({
    file: indexFile,
    before: indexBefore,
    after: encode({ version: 1, assets: index }),
  });
  for (const change of changes) {
    for (const [folder, bytes] of [
      ["before", change.before],
      ["after", change.after],
    ] as const) {
      const target = path.join(output, folder, change.file);
      await fs.mkdir(path.dirname(target), { recursive: true });
      await fs.writeFile(target, bytes, { flag: "wx" });
    }
  }
  const report = {
    scope: reviewedPhysicalAssets
      ? "reviewed-physical-incomplete-gameplay-draft-publication"
      : "incomplete-gameplay-draft-publication",
    physicalReviews,
    published,
    skipped,
    scenes,
    applied: false,
  };
  await fs.writeFile(path.join(output, "report.json"), encode(report));
  if (apply) {
    for (const model of reviewedModels.values())
      if (sha(await fs.readFile(path.join(library, model.model))) !== model.sha)
        throw new Error(`Reviewed model changed during publication: ${model.model}`);
    // Preflight every byte before any mutation; the index is installed last.
    for (const change of changes)
      if ((await fs.readFile(path.join(library, change.file), "utf8")) !== change.before)
        throw new Error(`Library changed during publication: ${change.file}`);
    const installed: Change[] = [];
    try {
      for (const change of changes) {
        const target = path.join(library, change.file);
        await fs.writeFile(target + ".gameplay-draft.tmp", change.after, { flag: "wx" });
        await fs.rename(target + ".gameplay-draft.tmp", target);
        installed.push(change);
      }
    } catch (error) {
      for (const change of installed.reverse())
        await fs.writeFile(path.join(library, change.file), change.before);
      throw error;
    }
    report.applied = true;
    await fs.writeFile(path.join(output, "report.json"), encode(report));
  }
  return report;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const [library, drafts, output, mode] = process.argv.slice(2);
  if (!library || !drafts || !output || (mode !== undefined && mode !== "--apply"))
    throw new Error(
      "Usage: publish-gameplay-drafts.ts library draft-libraries new-backup-directory [--apply]",
    );
  const report = await publishGameplayDrafts(library, drafts, output, mode === "--apply");
  console.log(
    JSON.stringify({
      published: report.published.length,
      skipped: report.skipped.length,
      scenes: report.scenes,
      applied: report.applied,
    }),
  );
}
