import { CatmullRomCurve3, Vector3 } from "three";
import { gameToScene, type MapCamera } from "./scene.ts";
import type { LevelSpline } from "./splines.ts";

export function splineCurve(path: LevelSpline, camera: MapCamera) {
  const curve = new CatmullRomCurve3(
    path.points.map((p) => new Vector3(...gameToScene(camera, ...p))),
    path.closed,
    "centripetal",
  );
  curve.arcLengthDivisions = Math.max(256, path.points.length * 40);
  curve.updateArcLengths();
  return curve;
}

/** Curve parameter, not normalized arc distance: endpoints must match their handles. */
export function splineSectionAt(path: LevelSpline, parameter: number) {
  const count = path.closed ? path.points.length : path.points.length - 1;
  const scaled = Math.max(0, Math.min(1, parameter)) * count;
  const section = Math.min(count - 1, Math.floor(scaled));
  return { section, fraction: scaled - section, next: (section + 1) % path.points.length };
}

export function splineWidthAt(path: LevelSpline, parameter: number) {
  const { section, fraction, next } = splineSectionAt(path, parameter);
  const a = path.pointWidths?.[section] ?? path.width;
  const b = path.pointWidths?.[next] ?? path.width;
  return a + (b - a) * fraction;
}

export function splineMaterialWeightsAt(
  path: LevelSpline,
  parameter: number,
): Record<string, number> {
  const { section, fraction, next } = splineSectionAt(path, parameter);
  const weights: Record<string, number> = {};
  for (const [index, weight] of [
    [section, 1 - fraction],
    [next, fraction],
  ] as const) {
    const mix = path.pointMaterialMixes?.[index] ?? {
      [path.pointMaterials?.[index] ?? (path.kind === "river" ? "water_still" : "path_dirt")]: 1,
    };
    for (const [id, value] of Object.entries(mix))
      weights[id] = (weights[id] ?? 0) + value * weight;
  }
  return weights;
}

export function sampleSpline(path: LevelSpline, camera: MapCamera) {
  const curve = splineCurve(path, camera),
    length = curve.getLength();
  const count = Math.min(4096, Math.max(8, Math.ceil(length / 12)));
  return Array.from({ length: count + 1 }, (_, i) => {
    const parameter = curve.getUtoTmapping(i / count, 0);
    const { section, next, fraction } = splineSectionAt(path, parameter);
    return {
      position: curve.getPoint(parameter),
      tangent: curve.getTangent(parameter),
      width: splineWidthAt(path, parameter),
      heightOffset:
        (path.pointHeightOffsets?.[section] ?? 0) * (1 - fraction) +
        (path.pointHeightOffsets?.[next] ?? 0) * fraction,
      ...splineSectionAt(path, parameter),
      distance: (i / count) * length,
    };
  });
}
