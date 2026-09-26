/** Validate and migrate all active library maps to descriptor-backed placements. */
import fs from "node:fs/promises";
import path from "node:path";
import { isDeepStrictEqual } from "node:util";
import { parseStoredMap, serializeStoredMap } from "@rle/shared";
import { pinnedDescriptors, readStoredMap } from "./stored-map.ts";

const [library, action] = process.argv.slice(2);
if (!library || (action !== undefined && action !== "--apply"))
  throw new Error("Usage: migrate-map-v2.ts <library> [--apply]");
const scenes = path.join(library, "scenes");
const names = (await fs.readdir(scenes)).filter((name) => name.endsWith(".rhlos-map.json")).sort();
const changes: { file: string; before: string; after: string }[] = [];
for (const name of names) {
  const file = path.join(scenes, name);
  const before = await fs.readFile(file, "utf8");
  const document = await readStoredMap(file, library);
  const descriptors = await pinnedDescriptors(library, document.assetSources ?? []);
  const stored = serializeStoredMap(document, descriptors);
  const restored = parseStoredMap(stored, descriptors);
  if (!isDeepStrictEqual(restored, document))
    throw new Error(`Map changed during serialization: ${name}`);
  const after = JSON.stringify(stored, null, 2) + "\n";
  if (after !== before) changes.push({ file, before, after });
}
const report = {
  maps: names.length,
  converted: changes.length,
  bytesBefore: changes.reduce((n, item) => n + Buffer.byteLength(item.before), 0),
  bytesAfter: changes.reduce((n, item) => n + Buffer.byteLength(item.after), 0),
};
if (action === "--apply" && changes.length) {
  const backup = path.join(
    scenes,
    "backups",
    `map-v2-${new Date().toISOString().replaceAll(/[:.]/g, "")}`,
  );
  await fs.mkdir(backup, { recursive: true });
  for (const item of changes)
    await fs.writeFile(path.join(backup, path.basename(item.file)), item.before);
  try {
    for (const item of changes) {
      const temporary = `${item.file}.map-v2-tmp`;
      await fs.writeFile(temporary, item.after);
      await fs.rename(temporary, item.file);
    }
  } catch (error) {
    for (const item of changes) await fs.writeFile(item.file, item.before);
    throw error;
  }
  console.log(JSON.stringify({ ...report, backup }, null, 2));
} else console.log(JSON.stringify(report, null, 2));
