import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { parseProjectionAssetDescriptor } from "@rle/shared";
import { sha256 } from "./bundle-asset-states.ts";
import { mergeStaticAssets, type StaticAssetInput } from "./merge-static-assets.ts";
import { splitStaticAsset } from "./split-static-asset.ts";
import { readStoredMap, compactStoredMap } from "./stored-map.ts";
import type { GameplayOwnershipCatalog } from "./nonrendering-gameplay-owners.ts";

/** Stage an isolated library overlay; the published library is never modified. */
export async function stageCanonicalStaticAsset(options: {
  library: string;
  map: string;
  catalog: string;
  id: string;
  out: string;
  split?: boolean;
}) {
  const library = path.resolve(options.library);
  const out = path.resolve(options.out);
  if (out === library || out.startsWith(`${library}${path.sep}`))
    throw new Error("Staging output must be outside the published library");
  let document = await readStoredMap(options.map, library);
  const catalog: GameplayOwnershipCatalog = JSON.parse(await fs.readFile(options.catalog, "utf8"));
  const group = catalog.groups.find((entry) => entry.id === options.id);
  if (!group || group.parts.some((part) => part.obstacle === undefined))
    throw new Error("Expected a catalog group of obstacle parts");
  const expected = group.parts.map((part) => part.obstacle!);
  const assets = new Set(
    document.objects
      .filter(
        (part) => part.source.obstacle !== undefined && expected.includes(part.source.obstacle),
      )
      .map((part) => part.node.split(":")[1]),
  );
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  const inputs: StaticAssetInput[] = [];
  for (const id of assets) {
    const reference = document.assetSources?.find((entry) => entry.id === id);
    if (!reference) throw new Error(`Missing pinned asset: ${id}`);
    const raw = JSON.parse(await fs.readFile(path.join(library, reference.descriptor), "utf8"));
    // Parsing validates the descriptor; retain extension fields for migration rejection.
    const descriptor = { ...raw, ...parseProjectionAssetDescriptor(raw) };
    const modelPath = path.join(library, reference.model);
    if (sha256(await fs.readFile(modelPath)) !== reference.model_sha256)
      throw new Error(`Model changed: ${id}`);
    for (const resource of reference.resources ?? [])
      if (sha256(await fs.readFile(path.join(library, resource.path))) !== resource.sha256)
        throw new Error(`Model resource changed: ${resource.path}`);
    const json = await io.readAsJSON(modelPath);
    const known = new Set(ALL_EXTENSIONS.map((extension) => extension.EXTENSION_NAME));
    for (const extension of json.json.extensionsUsed ?? [])
      if (!known.has(extension)) throw new Error(`Unsupported model extension: ${extension}`);
    inputs.push({ descriptor, model: await io.readJSON(json) });
  }
  const remaining: Awaited<ReturnType<typeof splitStaticAsset>>["outputs"] = [];
  if (options.split)
    for (const [index, input] of inputs.entries()) {
      const selected = input.descriptor.parts.filter((part) =>
        expected.includes(part.source_obstacle!),
      );
      const other = input.descriptor.parts.filter(
        (part) => !expected.includes(part.source_obstacle!),
      );
      if (!other.length) continue;
      const split = await splitStaticAsset(document, input, [
        {
          id: `${input.descriptor.id}-selected`,
          obstacles: selected.map((part) => part.source_obstacle!),
        },
        {
          id: `${input.descriptor.id}-remainder`,
          obstacles: other.map((part) => part.source_obstacle!),
        },
      ]);
      document = split.document;
      inputs[index] = split.outputs[0]!;
      remaining.push(split.outputs[1]!);
    }
  const merged = await mergeStaticAssets(document, options.id, expected, inputs);
  const outputs = [merged, ...remaining];
  // Exclusive creation prevents accidental writes through a previous overlay's symlinks.
  await fs.mkdir(out);
  await fs.mkdir(path.join(out, "3d-assets"));
  await fs.mkdir(path.join(out, "scenes"));
  for (const entry of await fs.readdir(library))
    if (!["3d-assets", "scenes"].includes(entry))
      await fs.symlink(path.join(library, entry), path.join(out, entry));
  for (const entry of await fs.readdir(path.join(library, "3d-assets"))) {
    if (entry === "index.json") continue;
    if (outputs.some((output) => output.descriptor.id === entry))
      throw new Error(`Asset directory already exists: ${entry}`);
    await fs.symlink(path.join(library, "3d-assets", entry), path.join(out, "3d-assets", entry));
  }
  const index = JSON.parse(await fs.readFile(path.join(library, "3d-assets/index.json"), "utf8"));
  for (const output of outputs) {
    const assetDir = `3d-assets/${output.descriptor.id}`;
    await fs.mkdir(path.join(out, assetDir));
    const descriptorBytes = JSON.stringify(output.descriptor, null, 2) + "\n";
    await fs.writeFile(path.join(out, assetDir, "model.glb"), output.bytes);
    await fs.writeFile(path.join(out, assetDir, "asset.json"), descriptorBytes);
    index.assets.push({
      id: output.descriptor.id,
      name: output.descriptor.name,
      source_map: output.descriptor.source_map,
      descriptor: `${output.descriptor.id}/asset.json`,
      descriptor_sha256: sha256(descriptorBytes),
      model: `${output.descriptor.id}/model.glb`,
      model_sha256: sha256(output.bytes),
      model_scene: output.descriptor.model_scene,
      editor: output.descriptor,
    });
    merged.document.assetSources!.push({
      id: output.descriptor.id,
      descriptor: `${assetDir}/asset.json`,
      descriptor_sha256: sha256(descriptorBytes),
      model: `${assetDir}/model.glb`,
      model_sha256: sha256(output.bytes),
      model_scene: output.descriptor.model_scene,
      resources: [],
    });
  }
  await fs.writeFile(path.join(out, "3d-assets/index.json"), JSON.stringify(index, null, 2) + "\n");
  for (const entry of await fs.readdir(path.join(library, "scenes")))
    if (entry !== path.basename(options.map))
      await fs.symlink(path.join(library, "scenes", entry), path.join(out, "scenes", entry));
  const scenePath = path.join(out, "scenes", path.basename(options.map));
  await fs.writeFile(
    scenePath,
    JSON.stringify(await compactStoredMap(merged.document, out), null, 2) + "\n",
  );
  await readStoredMap(scenePath, out);
  return { library: out, scene: scenePath, asset: options.id, parts: expected.length };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [library, map, catalog, id, out, split] = process.argv.slice(2);
  if (!library || !map || !catalog || !id || !out)
    throw new Error("Usage: stage-canonical-static-asset.ts LIBRARY MAP CATALOG ID OUT [--split]");
  if (split && split !== "--split") throw new Error(`Unknown option: ${split}`);
  console.log(
    JSON.stringify(
      await stageCanonicalStaticAsset({
        library,
        map,
        catalog,
        id,
        out,
        split: split === "--split",
      }),
      null,
      2,
    ),
  );
}
