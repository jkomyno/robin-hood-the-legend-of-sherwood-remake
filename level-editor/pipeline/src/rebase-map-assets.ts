import { parseLevel3D } from "@rle/shared";
import { rebaseLibraryRevision } from "./refined-map-groups.ts";
import { compactStoredMap, pinnedDescriptors, readStoredMap } from "./stored-map.ts";
const [previous, previousLibrary, revised, revisedLibrary] = process.argv.slice(2);
if (!previous || !previousLibrary || !revised || !revisedLibrary)
  throw new Error(
    "Usage: rebase-map-assets.ts <previous.json> <previous-library> <revised.json> <revised-library>",
  );
const document = await readStoredMap(previous, previousLibrary);
const staged = await readStoredMap(revised, revisedLibrary);
async function origins(map: typeof document, library: string) {
  const descriptors = await pinnedDescriptors(library, map.assetSources ?? []);
  return Object.fromEntries(
    [...descriptors].map(([id, descriptor]) => {
      const origin =
        descriptor.source_origin_scene ??
        (map.sceneMetadata?.assetOrigins as Record<string, [number, number, number]> | undefined)?.[
          id
        ];
      if (!origin) throw new Error(`Missing pinned asset export origin: ${id}`);
      return [id, origin];
    }),
  );
}
console.log(
  JSON.stringify(
    await compactStoredMap(
      parseLevel3D(
        rebaseLibraryRevision(
          document,
          staged,
          await origins(document, previousLibrary),
          await origins(staged, revisedLibrary),
        ),
      ),
      revisedLibrary,
    ),
  ),
);
