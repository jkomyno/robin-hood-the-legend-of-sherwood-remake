import type { LevelSpline } from "@rle/shared";
import { cornerAssetIds } from "./spline-corners.ts";
export type WallPreset = Pick<
  LevelSpline,
  | "name"
  | "asset"
  | "axis"
  | "sourceAngle"
  | "sourceStraight"
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
export function wallPreset(path: WallPreset): WallPreset {
  const {
    name,
    asset,
    axis,
    sourceAngle,
    sourceStraight,
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
  const result = {
    name,
    asset,
    axis,
    sourceAngle,
    sourceStraight,
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
  if (cornerAsset && !cornerAssetIds.has(cornerAsset)) {
    result.cornerAsset = undefined;
    result.cornerMinAngle = undefined;
    result.cornerScale = undefined;
    result.cornerWidthScale = undefined;
    result.cornerRotation = undefined;
  }
  return result;
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
