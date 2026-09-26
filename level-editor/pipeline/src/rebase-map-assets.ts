import { parseLevel3D } from "@rle/shared";
import { rebaseLibraryRevision } from "./refined-map-groups.ts";
import { compactStoredMap, readStoredMap } from "./stored-map.ts";
import path from "node:path";
const [previous, revised] = process.argv.slice(2);
if (!previous || !revised)
  throw new Error("Usage: rebase-map-assets.ts <previous.json> <revised.json>");
const document = await readStoredMap(previous, path.resolve(path.dirname(previous), ".."));
const staged = await readStoredMap(revised, path.resolve(path.dirname(revised), ".."));
console.log(
  JSON.stringify(
    await compactStoredMap(
      parseLevel3D(rebaseLibraryRevision(document, staged)),
      path.resolve(path.dirname(revised), ".."),
    ),
  ),
);
