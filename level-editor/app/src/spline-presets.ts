import type { ProjectionAssetEntry } from "@rle/shared";
import type { WallPreset } from "./wall-presets";
import catalog from "./assets/wall-presets.json";

export const builtInWallPresets: (WallPreset & { source_map: string })[] = catalog.map(
  (preset) => ({ ...preset, axis: "x" }),
);

// Standalone towers checked independently of the compound curtain-wall assets.
export const cornerAssetIds = new Set([
  "derby-lower-west-wall-turret",
  "leicester-east-moat-tower",
  "leicester-west-moat-tower",
  "lincoln-east-gate-north-tower",
  "lincoln-east-gate-south-tower",
  "nottingham-castle-east-round-tower",
  "nottingham-northwest-round-tower",
  "nottingham-northeast-round-tower",
  "nottingham-south-gate-west-tower",
]);
export function availableWallPresets(entries: ProjectionAssetEntry[]) {
  const ids = new Set(entries.map((entry) => entry.id));
  return builtInWallPresets.filter((preset) => ids.has(preset.asset!));
}
