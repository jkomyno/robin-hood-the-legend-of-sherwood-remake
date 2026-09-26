import type { LevelSpline } from "@rle/shared";
export type WallPreset = Pick<
  LevelSpline,
  | "name"
  | "asset"
  | "axis"
  | "sourceAngle"
  | "sourceStart"
  | "sourceEnd"
  | "flipCrossSection"
  | "width"
  | "repeatLength"
  | "cornerAsset"
  | "cornerMinAngle"
  | "cornerScale"
  | "cornerWidthScale"
  | "cornerRotation"
>;
export function wallPreset(path: LevelSpline): WallPreset {
  const {
    name,
    asset,
    axis,
    sourceAngle,
    sourceStart,
    sourceEnd,
    flipCrossSection,
    width,
    repeatLength,
    cornerAsset,
    cornerMinAngle,
    cornerScale,
    cornerWidthScale,
    cornerRotation,
  } = path;
  return {
    name,
    asset,
    axis,
    sourceAngle,
    sourceStart,
    sourceEnd,
    flipCrossSection,
    width,
    repeatLength,
    cornerAsset,
    cornerMinAngle,
    cornerScale,
    cornerWidthScale,
    cornerRotation,
  };
}
export function readWallPresets(): WallPreset[] {
  const raw = localStorage.getItem("rle.wallPresets");
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (
      !Array.isArray(parsed) ||
      parsed.some(
        (p) =>
          typeof p.name !== "string" ||
          typeof p.asset !== "string" ||
          !Number.isFinite(p.width) ||
          p.width <= 0 ||
          !Number.isFinite(p.repeatLength) ||
          p.repeatLength < 1,
      )
    )
      throw new Error("Invalid wall presets");
    return parsed.map((p) => wallPreset(p));
  } catch (error) {
    console.warn("Could not load saved wall presets", error);
    return [];
  }
}
