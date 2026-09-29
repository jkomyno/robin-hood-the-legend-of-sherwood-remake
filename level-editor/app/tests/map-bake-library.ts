import { openHttpLibrary } from "../src/http-library.ts";
import { prepareMapCandidate } from "../src/map-candidate.ts";
import { EditorViewport } from "../src/editor-viewport.ts";
import { packageCompiledMap } from "../src/map-compile.ts";
import { readPinnedAssetDescriptors } from "../src/projection-library.ts";

const result = document.querySelector("#result")!;
let viewport: EditorViewport | undefined;
try {
  const name = new URLSearchParams(location.search).get("map") ?? "leicester";
  const library = await openHttpLibrary("/library/");
  const candidate = await prepareMapCandidate(name, library.handle, null, (count, total) => {
    result.textContent = `RUNNING loading ${count}/${total}`;
  });
  viewport = new EditorViewport({
    document: () => candidate.document,
    selection: () => null,
    level: () => null,
    showObstacles: () => false,
    showElevation: () => false,
    onSelection: () => {},
    commitTransform: () => {},
  });
  viewport.replaceMap(
    candidate.asset,
    candidate.ground,
    candidate.sources,
    candidate.document.assetSources,
  );
  const assets = await readPinnedAssetDescriptors(
    library.handle,
    candidate.document.assetSources ?? [],
    candidate.document.sceneAssets,
  );
  const { compiled, pixels, appearance } = viewport.bakeMap(candidate.document, assets);
  const archive = await packageCompiledMap(compiled, pixels, appearance);
  (window as unknown as { __bakeZip: number[] }).__bakeZip = Array.from(archive);
  result.textContent = `PASS ${name}: ${compiled.bounds[2]}x${compiled.bounds[3]}, ${compiled.descriptor.volumes.length} volumes, ${archive.length} ZIP bytes`;
} catch (error) {
  result.textContent = `FAIL ${error instanceof Error ? error.stack : String(error)}`;
} finally {
  viewport?.dispose();
}
