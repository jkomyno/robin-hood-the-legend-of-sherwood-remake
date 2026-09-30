import { openHttpLibrary } from "../src/http-library.ts";
import { prepareMapCandidate } from "../src/map-candidate.ts";
import { disposeObjectResources } from "../src/resources.ts";

const result = document.querySelector("#result")!;
try {
  const query = new URLSearchParams(location.search);
  const library = await openHttpLibrary(query.get("library") ?? "/library/");
  const maps = (query.get("maps") ?? "derby").split(",");
  const loaded: string[] = [];
  for (const map of maps) {
    const candidate = await prepareMapCandidate(map, library.handle, null, (count, total) => {
      result.textContent = `RUNNING ${map} ${count}/${total}`;
    });
    try {
      if (!candidate.document.objects.length || !candidate.sources.size)
        throw new Error(`${map}: empty loaded scene`);
      loaded.push(`${map} (${candidate.sources.size} parts)`);
    } finally {
      disposeObjectResources([candidate.asset]);
    }
  }
  result.textContent = `PASS ${loaded.join(", ")}`;
} catch (error) {
  result.textContent = `FAIL ${error instanceof Error ? error.stack : String(error)}`;
}
