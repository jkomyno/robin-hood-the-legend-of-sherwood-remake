import fs from "node:fs/promises";
import { parseLevel3D } from "@rle/shared";
import { rebaseLibraryRevision } from "./refined-map-groups.ts";
const [previous, revised] = process.argv.slice(2);
if (!previous || !revised) throw new Error("Usage: rebase-map-assets.ts <previous.json> <revised.json>");
const document = parseLevel3D(JSON.parse(await fs.readFile(previous, "utf8")));
const staged = parseLevel3D(JSON.parse(await fs.readFile(revised, "utf8")));
console.log(JSON.stringify(parseLevel3D(rebaseLibraryRevision(document, staged))));
