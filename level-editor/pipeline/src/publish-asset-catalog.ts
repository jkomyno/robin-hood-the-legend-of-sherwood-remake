/** Assign explicit reviewed ownership to a pristine JSON map. */
import { readFile, writeFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { parseLevel3D, upgradeGeneratedAssetGroups, type AuthoredAssetCatalog } from "@rle/shared";
import { sceneAssetNodes } from "./scene-assets.ts";

const [documentArg, catalogArg] = process.argv.slice(2);
if (!documentArg || !catalogArg)
  throw new Error(
    "Usage: node publish-asset-catalog.ts <map.rhlos-map.json> <reviewed-catalog.json>",
  );
const output = resolve(documentArg);
const previous = await readFile(output, "utf8");
const document = parseLevel3D(JSON.parse(previous));
const catalog = JSON.parse(await readFile(resolve(catalogArg), "utf8")) as AuthoredAssetCatalog;
const model = await sceneAssetNodes(dirname(dirname(output)), document);
if (!upgradeGeneratedAssetGroups(document, catalog))
  throw new Error("Document has custom ownership or edits; refusing to replace it");
parseLevel3D(document, { nodes: new Set(model.nodes.map((node) => node.name).filter(Boolean)) });
await writeFile(output + ".before-asset-catalog", previous, { flag: "wx" });
if ((await readFile(output, "utf8")) !== previous)
  throw new Error("Map changed during publication");
await writeFile(output, JSON.stringify(document, null, 2) + "\n");
console.log(
  JSON.stringify({ file: output, assets: document.groups.length, parts: document.objects.length }),
);
