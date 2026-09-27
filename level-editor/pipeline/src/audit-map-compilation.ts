/** Check every saved scene using only its pinned library assets. */
import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import {
  expandStoredMap,
  parseStoredMap,
  type ExternalAssetSource,
  type SceneAssetSource,
} from "@rle/shared";
import { pinnedDescriptors } from "./stored-map.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import type { GameplayAssetDescriptor } from "../../shared/src/asset-gameplay.ts";

export async function auditMapCompilation(library: string) {
  const scenes = path.join(library, "scenes");
  const results = [];
  for (const name of (await fs.readdir(scenes))
    .filter((n) => n.endsWith(".rhlos-map.json"))
    .sort()) {
    const entry: {
      file: string;
      ready: boolean;
      assets: number;
      missingGameplay: string[];
      error?: string;
    } = {
      file: name,
      ready: false,
      assets: 0,
      missingGameplay: [],
    };
    try {
      const raw: unknown = JSON.parse(await fs.readFile(path.join(scenes, name), "utf8"));
      const saved = expandStoredMap(raw);
      const descriptors = await pinnedDescriptors(
        library,
        (saved.assetSources as ExternalAssetSource[] | undefined) ?? [],
        (saved.sceneAssets as SceneAssetSource[] | undefined) ?? [],
      );
      entry.assets = descriptors.size;
      entry.missingGameplay = [...descriptors]
        .filter(([, d]) => !(d as GameplayAssetDescriptor).gameplay)
        .map(([id]) => id)
        .sort();
      const document = parseStoredMap(raw, descriptors);
      const bounds =
        document.exportBounds ??
        (document.size
          ? ([0, 0, document.size[0], document.size[1]] as [number, number, number, number])
          : undefined);
      if (!bounds) throw new Error("Map has no export bounds or authored size");
      compileAssetGameplay(document, descriptors, bounds);
      entry.ready = true;
    } catch (error) {
      entry.error = error instanceof Error ? error.message : String(error);
    }
    results.push(entry);
  }
  return {
    version: 1,
    maps: results.length,
    ready: results.filter((r) => r.ready).length,
    results,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const { values } = parseArgs({
    options: {
      library: { type: "string", default: "../library" },
      out: { type: "string" },
    },
  });
  const report = await auditMapCompilation(values.library);
  if (values.out) {
    await fs.mkdir(path.dirname(values.out), { recursive: true });
    await fs.writeFile(values.out, JSON.stringify(report, null, 2) + "\n");
  }
  for (const result of report.results)
    console.log(
      `${result.ready ? "PASS" : "FAIL"} ${result.file}: ${result.assets} assets, ${result.missingGameplay.length} missing gameplay${result.error ? `; ${result.error.slice(0, 160)}` : ""}`,
    );
  console.log(`${report.ready}/${report.maps} maps compile from assets`);
  if (!report.maps || report.ready !== report.maps) process.exitCode = 1;
}
