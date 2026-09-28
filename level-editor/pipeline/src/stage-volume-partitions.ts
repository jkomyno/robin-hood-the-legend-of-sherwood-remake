import fs from "node:fs/promises";
import path from "node:path";
import { isDeepStrictEqual, parseArgs } from "node:util";
import { pathToFileURL } from "node:url";
import { parseProjectionAssetDescriptor, safeLibraryPath } from "@rle/shared";
import { readStoredMap, pinnedDescriptors, compactStoredMap } from "./stored-map.ts";
import { sha256 } from "./bundle-asset-states.ts";

/** Install reviewed draft metadata in an isolated overlay, retaining model/resource paths. */
export async function stageVolumePartitions(options: {
  library: string;
  map: string;
  draft: string;
  out: string;
}) {
  const library = path.resolve(options.library),
    out = path.resolve(options.out);
  if (out === library || out.startsWith(library + path.sep))
    throw new Error("Draft overlay must be outside its source library");
  const manifest: {
    parts: { asset: string; descriptor_sha256: string; model_sha256: string }[];
    descriptors: { id: string; path: string; sha256: string }[];
  } = JSON.parse(await fs.readFile(path.join(options.draft, "partition-review.json"), "utf8"));
  if (
    !manifest.descriptors.length ||
    new Set(manifest.descriptors.map((d) => d.id)).size !== manifest.descriptors.length
  )
    throw new Error("Expected distinct partition draft descriptors");
  const document = await readStoredMap(options.map, library);
  const originals = await pinnedDescriptors(
    library,
    document.assetSources ?? [],
    document.sceneAssets,
  );
  const index = JSON.parse(await fs.readFile(path.join(library, "3d-assets/index.json"), "utf8"));
  const replacements = new Map<string, string>();
  for (const entry of manifest.descriptors) {
    const reference = document.assetSources?.find((a) => a.id === entry.id);
    const original = originals.get(entry.id);
    const owners = manifest.parts.filter((p) => p.asset === entry.id);
    if (
      !reference ||
      !original ||
      !owners.length ||
      owners.some(
        (p) =>
          p.descriptor_sha256 !== reference.descriptor_sha256 ||
          p.model_sha256 !== reference.model_sha256,
      )
    )
      throw new Error(`Partition input descriptor/model pins changed: ${entry.id}`);
    if (!safeLibraryPath(entry.path)) throw new Error("Invalid partition draft path");
    const bytes = await fs.readFile(path.join(options.draft, entry.path));
    if (
      sha256(bytes) !== entry.sha256 ||
      sha256(await fs.readFile(path.join(library, reference.model))) !== reference.model_sha256
    )
      throw new Error(`Partition draft or model bytes changed: ${entry.id}`);
    const raw = JSON.parse(bytes.toString());
    const descriptor = parseProjectionAssetDescriptor(raw);
    if (
      descriptor.id !== entry.id ||
      descriptor.model !== original.model ||
      !isDeepStrictEqual(descriptor.resources, original.resources) ||
      !isDeepStrictEqual(
        descriptor.parts.map((p) => p.node),
        original.parts.map((p) => p.node),
      )
    )
      throw new Error(`Partition draft changes asset identity or resources: ${entry.id}`);
    for (const object of document.objects.filter((p) => p.node.startsWith(`asset:${entry.id}:`))) {
      const node = object.node.slice(`asset:${entry.id}:`.length);
      const before = original.parts.find((p) => p.node === node)!;
      const after = descriptor.parts.find((p) => p.node === node)!;
      if (!isDeepStrictEqual(before.obstacle_local_game, after.obstacle_local_game)) {
        if (!isDeepStrictEqual(object.obstacle, before.obstacle_local_game))
          throw new Error(`Partition would overwrite a scene collision override: ${object.id}`);
        object.obstacle = structuredClone(after.obstacle_local_game);
      }
    }
    const entries = index.assets.filter((a: { id: string }) => a.id === entry.id);
    if (entries.length > 1) throw new Error(`Expected one indexed asset: ${entry.id}`);
    if (!entries.length) {
      if (
        !reference.descriptor.startsWith("3d-assets/") ||
        !reference.model.startsWith("3d-assets/")
      )
        throw new Error(`Scene asset cannot be indexed under 3d-assets: ${entry.id}`);
      const added = {
        id: entry.id,
        name: descriptor.name,
        source_map: descriptor.source_map,
        descriptor: reference.descriptor.slice("3d-assets/".length),
        model: reference.model.slice("3d-assets/".length),
        descriptor_sha256: reference.descriptor_sha256,
        model_sha256: reference.model_sha256,
        ...(reference.model_scene ? { model_scene: reference.model_scene } : {}),
      };
      index.assets.push(added);
      entries.push(added);
    }
    if (
      `3d-assets/${entries[0].descriptor}` !== reference.descriptor ||
      `3d-assets/${entries[0].model}` !== reference.model ||
      (entries[0].descriptor_sha256 !== undefined &&
        entries[0].descriptor_sha256 !== reference.descriptor_sha256)
    )
      throw new Error(`Partition index differs from the pinned scene: ${entry.id}`);
    entries[0].descriptor_sha256 = entry.sha256;
    entries[0].editor = raw;
    reference.descriptor_sha256 = entry.sha256;
    replacements.set(reference.descriptor, bytes.toString());
  }
  const scene = `scenes/${path.basename(options.map)}`;
  replacements.set("3d-assets/index.json", JSON.stringify(index, null, 2) + "\n");
  replacements.set(scene, "");
  const pending = new Set(replacements.keys());
  // Create real directories only along changed paths; no writes traverse shared symlinks.
  const overlay = async (relative: string) => {
    const destination = path.join(out, relative);
    await fs.mkdir(destination);
    for (const entry of await fs.readdir(path.join(library, relative))) {
      const child = relative ? relative + "/" + entry : entry;
      const replacement = replacements.get(child);
      if (replacement !== undefined) {
        await fs.writeFile(path.join(out, child), replacement);
        pending.delete(child);
      } else if ([...replacements.keys()].some((p) => p.startsWith(child + "/")))
        await overlay(child);
      else await fs.symlink(path.join(library, child), path.join(out, child));
    }
  };
  await overlay("");
  if (pending.size)
    throw new Error(`Partition overlay paths are missing: ${[...pending].join(", ")}`);
  const saved = path.join(out, scene);
  await fs.writeFile(saved, JSON.stringify(await compactStoredMap(document, out), null, 2) + "\n");
  await readStoredMap(saved, out);
  return { library: out, scene: saved, assets: manifest.descriptors.length };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const { values } = parseArgs({
    options: {
      library: { type: "string" },
      map: { type: "string" },
      draft: { type: "string" },
      out: { type: "string" },
    },
  });
  if (!values.library || !values.map || !values.draft || !values.out)
    throw new Error(
      "Usage: --library LIBRARY --map SCENE --draft PARTITION_DRAFT --out NEW_DIRECTORY",
    );
  console.log(
    JSON.stringify(
      await stageVolumePartitions({
        library: values.library,
        map: values.map,
        draft: values.draft,
        out: values.out,
      }),
    ),
  );
}
