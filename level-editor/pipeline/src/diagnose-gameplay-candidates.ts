import type { Level3D } from "@rle/shared";
import type { GameplayAssetDescriptor } from "../../shared/src/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";

/** Authoring diagnostics only. A static probe must never authorize a full export. */
export function diagnoseGameplayCandidates(
  document: Level3D,
  candidates: ReadonlyMap<string, GameplayAssetDescriptor>,
) {
  const bounds =
    document.exportBounds ??
    (document.size
      ? ([0, 0, document.size[0], document.size[1]] as [number, number, number, number])
      : undefined);
  const probe = (scene: Level3D): { ready: boolean; error?: string } => {
    try {
      if (!bounds) throw new Error("Map has no export bounds or size");
      compileAssetGameplay(scene, candidates, bounds);
      return { ready: true };
    } catch (error) {
      return { ready: false, error: String(error) };
    }
  };
  const compilation = probe(document);
  // Preserve the currently visible placement geometry. Removing unsupported
  // behaviours is confined to this disposable diagnostic snapshot.
  const staticScene = structuredClone(document);
  delete staticScene.population;
  delete staticScene.splines;
  for (const group of staticScene.groups) {
    delete group.states;
    delete group.patches;
  }
  for (const part of staticScene.objects) delete part.patches;
  return {
    compilation,
    staticGeometry: { scope: "current-visible-geometry-only", ...probe(staticScene) },
  };
}
