import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { pathToFileURL } from "node:url";
import {
  parseProjectionAssetDescriptor,
  parseProjectionAssetIndex,
} from "../../shared/src/validation.ts";
import { safeLibraryPath } from "../../shared/src/projection-assets.ts";
import { parseStoredMap } from "../../shared/src/stored-level.ts";
import { readStoredMap, pinnedDescriptors } from "./stored-map.ts";
import { mergeGameplayDraft } from "./publish-gameplay-drafts.ts";
import { transformedObstacle, type Level3D } from "../../shared/src/level3d.ts";

interface Placement {
  id: string;
  assets: string[];
}
interface Reference {
  id: string;
  descriptor: string;
  descriptor_sha256: string;
  model?: string;
  model_sha256?: string;
  model_scene?: string;
}
interface StoredScene {
  placements: Placement[];
  assetSources: Reference[];
  camera: unknown;
  size: unknown;
}
export interface DraftAddition {
  map: string;
  assets: string[];
  /** Explicitly reviewed regrouping; every replaced obstacle must survive in world space. */
  replacePlacements?: string[];
}

export function verifyReplacementGeometry(
  live: Level3D,
  staged: Level3D,
  removed: ReadonlySet<string>,
  added: ReadonlySet<string>,
) {
  const previous = live.objects.filter((o) => removed.has(o.group ?? o.id));
  const replacements = staged.objects.filter((o) => added.has(o.group ?? o.id));
  if (!previous.length || previous.length !== replacements.length)
    throw new Error("Replacement family has different part counts");
  const used = new Set<string>();
  for (const part of previous) {
    if (!part.obstacle || part.source?.obstacle === undefined)
      throw new Error(`Replacement requires reviewed obstacle identity: ${part.id}`);
    const candidates = replacements.filter((p) => p.source?.obstacle === part.source?.obstacle);
    const replacement = candidates[0];
    if (candidates.length !== 1 || !replacement?.obstacle || used.has(replacement.id))
      throw new Error(`Replacement obstacle is missing or ambiguous: ${part.id}`);
    used.add(replacement.id);
    const a = transformedObstacle(live, part),
      b = transformedObstacle(staged, replacement);
    const { points: aPoints, ...aFlags } = a,
      { points: bPoints, ...bFlags } = b;
    if (
      !isDeepStrictEqual(aFlags, bFlags) ||
      aPoints.length !== bPoints.length ||
      aPoints.some((point, i) =>
        (["x", "y", "z_bottom", "z_top"] as const).some(
          (key) => Math.abs(point[key] - bPoints[i]![key]) > 1e-7,
        ),
      )
    )
      throw new Error(`Replacement changes world obstacle geometry or flags: ${part.id}`);
  }
  return previous.length;
}

export function replaceDraftPlacements(
  live: StoredScene,
  staged: StoredScene,
  ids: ReadonlySet<string>,
  removed: ReadonlySet<string>,
) {
  for (const id of removed) {
    if (
      live.placements.filter((p) => p.id === id).length !== 1 ||
      staged.placements.some((p) => p.id === id)
    )
      throw new Error(`Missing or conflicting replacement placement: ${id}`);
  }
  const placements = live.placements.filter((p) => !removed.has(p.id));
  const removedAssets = new Set(
    live.placements.filter((p) => removed.has(p.id)).flatMap((p) => p.assets),
  );
  for (const p of placements) for (const id of p.assets) removedAssets.delete(id);
  return appendDraftPlacements(
    {
      ...live,
      placements,
      assetSources: live.assetSources.filter((r) => !removedAssets.has(r.id)),
    },
    staged,
    ids,
  );
}

/** Append only new identities; existing placement values are never rewritten. */
export function appendDraftPlacements(
  live: StoredScene,
  staged: StoredScene,
  ids: ReadonlySet<string>,
) {
  if (!isDeepStrictEqual(live.camera, staged.camera) || !isDeepStrictEqual(live.size, staged.size))
    throw new Error("Draft scene camera or size differs from the current scene");
  const existing = new Map(live.placements.map((p) => [p.id, p]));
  for (const placement of staged.placements) {
    const current = existing.get(placement.id);
    if (current && !isDeepStrictEqual(current, placement))
      throw new Error(`Current placement differs from draft: ${placement.id}`);
  }
  const additions = staged.placements.filter((p) => p.assets.some((id) => ids.has(id)));
  for (const placement of additions) {
    if (existing.has(placement.id) || placement.assets.some((id) => !ids.has(id)))
      throw new Error(`Draft placement requires explicit reconciliation: ${placement.id}`);
    existing.set(placement.id, placement);
  }
  const references = staged.assetSources.filter((r) => ids.has(r.id));
  for (const id of ids) {
    if (
      live.assetSources.some((r) => r.id === id) ||
      references.filter((r) => r.id === id).length !== 1 ||
      !additions.some((p) => p.assets.includes(id))
    )
      throw new Error(`Missing or conflicting new draft placement/reference: ${id}`);
  }
  return {
    ...live,
    placements: [...live.placements, ...structuredClone(additions)],
    assetSources: [...live.assetSources, ...structuredClone(references)],
  };
}

const sha = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const encode = (value: unknown) => Buffer.from(JSON.stringify(value, null, 2) + "\n");
interface Change {
  file: string;
  before: Buffer | null;
  after: Buffer;
}
async function optionalRead(file: string): Promise<Buffer | null> {
  try {
    return await fs.readFile(file);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
}

/** Validate and copy additive draft assets and placements with exact rollback bytes. */
export async function addGameplayDrafts(
  library: string,
  drafts: string,
  selections: DraftAddition[],
  output: string,
  apply: boolean,
) {
  library = path.resolve(library);
  output = path.resolve(output);
  if (output === library || output.startsWith(library + path.sep))
    throw new Error("Backup must be outside the library");
  await fs.mkdir(output, { recursive: false });
  const indexFile = "3d-assets/index.json";
  const indexBefore = await fs.readFile(path.join(library, indexFile));
  const index = parseProjectionAssetIndex(JSON.parse(indexBefore.toString()));
  const ids = new Set(index.map((e) => e.id));
  const changes = new Map<string, Change>();
  const scenes: string[] = [];
  const published: string[] = [];
  const verifiedParts = new Map<string, number>();
  async function addFile(file: string, bytes: Buffer, allowIdentical = false) {
    if (!safeLibraryPath(file)) throw new Error(`Unsafe publication path: ${file}`);
    const before = await optionalRead(path.join(library, file));
    const planned = changes.get(file);
    if (planned) {
      if (!allowIdentical || !planned.after.equals(bytes))
        throw new Error(`Draft path collision: ${file}`);
      return;
    }
    if (before) {
      if (!allowIdentical || !before.equals(bytes))
        throw new Error(`Existing publication path: ${file}`);
      return;
    }
    changes.set(file, { file, before: null, after: bytes });
  }
  for (const selection of selections) {
    if (!/^[a-z0-9_-]+$/.test(selection.map)) throw new Error("Invalid draft map name");
    const staged = path.join(drafts, selection.map);
    const catalog = parseProjectionAssetIndex(
      JSON.parse(await fs.readFile(path.join(staged, indexFile), "utf8")),
    );
    const report = JSON.parse(
      await fs.readFile(path.join(staged, "gameplay-staging-report.json"), "utf8"),
    ) as { issues: { asset: string; issues: string[] }[] };
    const sceneFile = `scenes/${selection.map}.rhlos-map.json`;
    const sceneBefore = await fs.readFile(path.join(library, sceneFile));
    const liveScene = JSON.parse(sceneBefore.toString()) as StoredScene;
    const draftScene = JSON.parse(
      await fs.readFile(path.join(staged, sceneFile), "utf8"),
    ) as StoredScene;
    const current = await readStoredMap(path.join(library, sceneFile), library);
    const draftDocument = await readStoredMap(path.join(staged, sceneFile), staged);
    const selected = new Set(selection.assets);
    const removed = new Set(selection.replacePlacements ?? []);
    const next = removed.size
      ? replaceDraftPlacements(liveScene, draftScene, selected, removed)
      : appendDraftPlacements(liveScene, draftScene, selected);
    if (removed.size)
      verifiedParts.set(
        selection.map,
        verifyReplacementGeometry(
          current,
          draftDocument,
          removed,
          new Set(
            draftScene.placements
              .filter((p) => p.assets.some((id) => selected.has(id)))
              .map((p) => p.id),
          ),
        ),
      );
    const descriptors = await pinnedDescriptors(
      library,
      current.assetSources ?? [],
      current.sceneAssets,
    );
    for (const id of selection.assets) {
      if (ids.has(id)) throw new Error(`Existing draft asset identity: ${id}`);
      const entry = catalog.find((e) => e.id === id);
      if (!entry) throw new Error(`Missing selected draft: ${id}`);
      const file = "3d-assets/" + entry.descriptor;
      const bytes = await fs.readFile(path.join(staged, file));
      if (sha(bytes) !== entry.descriptor_sha256) throw new Error(`Stale draft descriptor: ${id}`);
      const raw = JSON.parse(bytes.toString());
      const descriptor = parseProjectionAssetDescriptor(raw);
      if (descriptor.state_variants)
        throw new Error(`State family requires explicit publication: ${id}`);
      const merged = mergeGameplayDraft(
        descriptor,
        descriptor,
        report.issues.find((item) => item.asset === id)?.issues ?? [],
      );
      const after = encode({ ...raw, gameplay: merged.gameplay });
      await addFile(file, after);
      const modelFile = "3d-assets/" + entry.model;
      const model = await fs.readFile(path.join(staged, modelFile));
      if (sha(model) !== entry.model_sha256) throw new Error(`Stale draft model: ${id}`);
      await addFile(modelFile, model);
      // Check resources both from the descriptor and directly from GLB URI references.
      for (const resource of descriptor.resources ?? []) {
        const data = await fs.readFile(path.join(staged, resource.path));
        if (sha(data) !== resource.sha256)
          throw new Error(`Stale draft resource: ${resource.path}`);
        await addFile(resource.path, data, true);
      }
      if (model.readUInt32LE(0) !== 0x46546c67 || model.readUInt32LE(16) !== 0x4e4f534a)
        throw new Error(`Invalid draft GLB: ${id}`);
      const gltf = JSON.parse(model.subarray(20, 20 + model.readUInt32LE(12)).toString()) as {
        images?: { uri?: string }[];
        buffers?: { uri?: string }[];
      };
      for (const item of [...(gltf.images ?? []), ...(gltf.buffers ?? [])]) {
        if (!item.uri || item.uri.startsWith("data:")) continue;
        const resource = path.posix.normalize(
          path.posix.join(path.posix.dirname(modelFile), item.uri),
        );
        if (!safeLibraryPath(resource)) throw new Error(`Unsafe model resource: ${item.uri}`);
        await addFile(resource, await fs.readFile(path.join(staged, resource)), true);
      }
      const pin = sha(after);
      const reference = next.assetSources.find((r) => r.id === id)!;
      if (
        reference.model !== modelFile ||
        reference.model_sha256 !== entry.model_sha256 ||
        (reference.model_scene ?? "default") !== (entry.model_scene ?? "default")
      )
        throw new Error(`Stale draft scene model reference: ${id}`);
      if (reference.descriptor !== file || reference.descriptor_sha256 !== entry.descriptor_sha256)
        throw new Error(`Stale draft scene reference: ${id}`);
      reference.descriptor_sha256 = pin;
      descriptors.set(id, merged);
      index.push({ ...entry, descriptor_sha256: pin, editor: merged });
      ids.add(id);
      published.push(id);
    }
    parseStoredMap(next, descriptors);
    changes.set(sceneFile, { file: sceneFile, before: sceneBefore, after: encode(next) });
    scenes.push(sceneFile);
  }
  parseProjectionAssetIndex({ version: 1, assets: index });
  changes.set(indexFile, {
    file: indexFile,
    before: indexBefore,
    after: Buffer.from(JSON.stringify({ version: 1, assets: index }) + "\n"),
  });
  for (const change of changes.values()) {
    for (const [folder, bytes] of [
      ["before", change.before],
      ["after", change.after],
    ] as const) {
      if (!bytes) continue;
      const file = path.join(output, folder, change.file);
      await fs.mkdir(path.dirname(file), { recursive: true });
      await fs.writeFile(file, bytes, { flag: "wx" });
    }
  }
  const report = {
    scope: verifiedParts.size
      ? "replacement-family-incomplete-gameplay-draft-publication"
      : "additive-incomplete-gameplay-draft-publication",
    verifiedObstacleParts: [...verifiedParts.values()].reduce((sum, count) => sum + count, 0),
    replacements: selections
      .filter((s) => s.replacePlacements?.length)
      .map((s) => ({
        map: s.map,
        removed: s.replacePlacements,
        assets: s.assets,
        verifiedObstacleParts: verifiedParts.get(s.map)!,
      })),
    published,
    scenes,
    applied: false,
    files: [...changes.values()].map((c) => ({
      file: c.file,
      before: c.before ? sha(c.before) : null,
      after: sha(c.after),
    })),
  };
  await fs.writeFile(path.join(output, "report.json"), encode(report));
  if (apply) {
    for (const change of changes.values()) {
      const current = await optionalRead(path.join(library, change.file));
      if (
        current === null ? change.before !== null : !change.before || !current.equals(change.before)
      )
        throw new Error(`Library changed during publication: ${change.file}`);
    }
    const installed: Change[] = [];
    try {
      for (const change of changes.values()) {
        const target = path.join(library, change.file),
          temporary = target + ".gameplay-add.tmp";
        await fs.mkdir(path.dirname(target), { recursive: true });
        await fs.writeFile(temporary, change.after, { flag: "wx" });
        try {
          await fs.rename(temporary, target);
        } catch (error) {
          await fs.unlink(temporary);
          throw error;
        }
        installed.push(change);
      }
    } catch (error) {
      for (const change of installed.reverse()) {
        const target = path.join(library, change.file);
        if (change.before) await fs.writeFile(target, change.before);
        else await fs.unlink(target);
      }
      throw error;
    }
    report.applied = true;
    await fs.writeFile(path.join(output, "report.json"), encode(report));
  }
  return report;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const [library, drafts, selectionFile, output, mode] = process.argv.slice(2);
  if (
    !library ||
    !drafts ||
    !selectionFile ||
    !output ||
    (mode !== undefined && mode !== "--apply")
  )
    throw new Error(
      "Usage: add-gameplay-drafts.ts library drafts selections.json new-backup-directory [--apply]",
    );
  const report = await addGameplayDrafts(
    library,
    drafts,
    JSON.parse(await fs.readFile(selectionFile, "utf8")),
    output,
    mode === "--apply",
  );
  console.log(
    JSON.stringify({
      published: report.published.length,
      scenes: report.scenes,
      applied: report.applied,
    }),
  );
}
