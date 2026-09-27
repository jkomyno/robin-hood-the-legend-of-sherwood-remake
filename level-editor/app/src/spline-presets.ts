import type { ProjectionAssetEntry } from "@rle/shared";
import type { WallPreset } from "./wall-presets";
import catalog from "./assets/wall-presets.json";

export const builtInWallPresets: (WallPreset & { source_map: string })[] = catalog.map(
  (preset) => ({ ...preset, axis: "x" }),
);

export { cornerAssetIds } from "./spline-corners";
export function availableWallPresets(entries: ProjectionAssetEntry[]) {
  const ids = new Set(entries.map((entry) => entry.id));
  return builtInWallPresets.filter((preset) => ids.has(preset.asset!));
}
