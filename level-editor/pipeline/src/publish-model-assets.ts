/** Merge a staged Blender asset pack into the reusable 3D model library. */
import { readFile, mkdir, copyFile, rename } from "node:fs/promises";
import { resolve, join } from "node:path";
import { validateAssetIndex, writeAssetIndex } from "./asset-index.ts";

interface Entry {
  id: string;
  name: string;
  source_map: string;
  descriptor: string;
  model: string;
  lossy_model?: string;
  preview_model?: string;
}
const [stageArg, destinationArg] = process.argv.slice(2);
if (!stageArg || !destinationArg)
  throw new Error("Usage: node publish-model-assets.ts <staged-pack> <library/3d-assets>");
const stage = resolve(stageArg),
  destination = resolve(destinationArg);
if (stage === destination) throw new Error("Stage and destination must differ");
const staged = JSON.parse(await readFile(join(stage, "index.json"), "utf8")) as {
  version: number;
  assets: Entry[];
};
if (staged.version !== 1 || !Array.isArray(staged.assets))
  throw new Error("Invalid staged asset index");
const seen = new Set<string>();
for (const entry of staged.assets) {
  if (
    !/^[a-z0-9-]+$/.test(entry.id) ||
    seen.has(entry.id) ||
    entry.descriptor !== `${entry.id}/asset.json` ||
    entry.model !== `${entry.id}/model.glb`
  )
    throw new Error(`Invalid asset entry: ${entry.id}`);
  seen.add(entry.id);
  const asset = JSON.parse(await readFile(join(stage, entry.descriptor), "utf8"));
  const glb = await readFile(join(stage, entry.model));
  const gltf = JSON.parse(glb.toString("utf8", 20, 20 + glb.readUInt32LE(12)));
  const nodes = new Set(gltf.nodes.map((node: { name: string }) => node.name));
  if (
    asset.version !== 1 ||
    asset.id !== entry.id ||
    asset.name !== entry.name ||
    !asset.parts.length ||
    !asset.parts.every(
      (p: { node: string; obstacle_local_game?: unknown }) =>
        nodes.has(p.node) && p.obstacle_local_game,
    )
  )
    throw new Error(`Incomplete asset: ${entry.id}`);
}
let old: { version: number; assets: Entry[] } = { version: 1, assets: [] };
try {
  old = JSON.parse(await readFile(join(destination, "index.json"), "utf8"));
} catch (error) {
  if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
}
if (old.version !== 1 || !Array.isArray(old.assets))
  throw new Error("Invalid destination asset index");
const entries = new Map(old.assets.map((entry) => [entry.id, entry]));
const files = new Map<string, string>();
for (const entry of staged.assets) {
  for (const file of [entry.model, entry.descriptor]) files.set(file, join(stage, file));
  for (const derivative of [entry.lossy_model, entry.preview_model]) {
    if (!derivative) continue;
    files.set(derivative, join(stage, derivative));
    files.set(derivative + ".receipt.json", join(stage, derivative + ".receipt.json"));
  }
  entries.set(entry.id, entry);
}
const index = {
  version: 1,
  assets: [...entries.values()].sort((a, b) => a.id.localeCompare(b.id)),
};
validateAssetIndex(destination, index, Object.fromEntries(files));
await mkdir(destination, { recursive: true });
for (const entry of staged.assets) await mkdir(join(destination, entry.id), { recursive: true });
for (const [file, source] of files) {
  await copyFile(source, join(destination, file + ".pending"));
  await rename(join(destination, file + ".pending"), join(destination, file));
}
writeAssetIndex(destination, index);
console.log(
  JSON.stringify({ assets: staged.assets.length, index: join(destination, "index.json") }),
);
