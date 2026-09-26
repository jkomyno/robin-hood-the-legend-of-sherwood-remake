/** Publish immutable scene assets, then atomically replace their map manifest. */
import { readFile, writeFile, rename, mkdir } from "node:fs/promises";
import { resolve, dirname, basename, join } from "node:path";
import { createHash } from "node:crypto";
import { parseLevel3D } from "@rle/shared";
import { mergeRefinedGroups } from "./refined-map-groups.ts";
import { sceneAssetNodes, readSceneAsset } from "./scene-assets.ts";

const [stagedArg, documentArg] = process.argv.slice(2);
if (!stagedArg || !documentArg) throw new Error("Usage: node publish-refined-map.ts <staged.level3d.json> <live.level3d.json>");
const documentPath = resolve(documentArg), library = dirname(dirname(documentPath));
const stagedPath = resolve(stagedArg);
const stagedLibrary = basename(dirname(stagedPath)) === "scenes" ? dirname(dirname(stagedPath)) : join(dirname(stagedPath), "map-assets");
const previousText = await readFile(documentPath,"utf8");
const document = parseLevel3D(JSON.parse(previousText));
const staged = parseLevel3D(JSON.parse(await readFile(stagedPath,"utf8")), {map:document.map});
const previous = await sceneAssetNodes(library,document);
const next = await sceneAssetNodes(stagedLibrary,staged);
const {nodes,...updates} = mergeRefinedGroups(document,previous,next);
document.sceneAssets = staged.sceneAssets;
parseLevel3D(document,{nodes});
const installed = new Set<string>();
const install = async (relative: string, bytes: Uint8Array) => {
  if (installed.has(relative)) return;
  const target = join(library,relative);
  await mkdir(dirname(target),{recursive:true});
  try { await writeFile(target,bytes,{flag:"wx"}); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
    if (!Buffer.from(bytes).equals(await readFile(target))) throw new Error(`Immutable asset changed: ${relative}`);
  }
  installed.add(relative);
};
for (const reference of document.sceneAssets) {
  const {bytes,resources} = await readSceneAsset(stagedLibrary,reference);
  for (const [relative,resource] of Object.entries(resources)) await install(relative,resource);
  await install(reference.model,bytes);
}
const backup = join(dirname(documentPath),"backups",createHash("sha256").update(previousText).digest("hex").slice(0,16));
await mkdir(backup,{recursive:true});
await writeFile(join(backup,basename(documentPath)),previousText);
if (await readFile(documentPath,"utf8") !== previousText) throw new Error("Map changed during publication; refusing to overwrite edits");
await writeFile(documentPath+".pending",JSON.stringify(document,null,2)+"\n",{flag:"wx"});
await rename(documentPath+".pending",documentPath);
console.log(JSON.stringify({document:documentPath,backup,assets:document.sceneAssets.length,parts:nodes.size,...updates}));
