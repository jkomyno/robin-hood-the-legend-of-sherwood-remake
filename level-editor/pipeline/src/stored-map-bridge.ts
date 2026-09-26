/** JSON stdin/stdout bridge for Python publication tools that inspect map parts. */
import { parseLevel3D, parseStoredMap, serializeStoredMap } from "@rle/shared";
import { pinnedDescriptors } from "./stored-map.ts";

const [action, library] = process.argv.slice(2);
if (!library || (action !== "expand" && action !== "store"))
  throw new Error("Usage: stored-map-bridge.ts <expand|store> <library>");
let input = "";
for await (const chunk of process.stdin) input += chunk.toString();
const raw = JSON.parse(input);
const descriptors = await pinnedDescriptors(library, raw.assetSources ?? []);
const result =
  action === "expand"
    ? parseStoredMap(raw, descriptors)
    : serializeStoredMap(parseLevel3D(raw), descriptors);
process.stdout.write(JSON.stringify(result));
