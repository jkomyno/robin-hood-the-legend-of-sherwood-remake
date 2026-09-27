import polygonClipping, { type MultiPolygon } from "polygon-clipping";
import { quantizeGeneratedMotionPolygon } from "./motion-quantization.ts";

/** Repair crossings introduced by snapping generated boundaries to the movement grid. */
export function normalizeGeneratedMotion(
  regions: MultiPolygon,
  label: string,
  warnings: string[],
  union: (regions: MultiPolygon) => MultiPolygon = (regions) => polygonClipping.union(regions),
): MultiPolygon {
  const seen = new Set<string>();
  for (let iteration = 0; iteration < 8; iteration++) {
    const rounded = regions.flatMap((region) => {
      const result = quantizeGeneratedMotionPolygon(region, Math.round, label, warnings);
      return result ? [result] : [];
    });
    if (!rounded.length) return [];
    const key = JSON.stringify(rounded);
    if (seen.has(key)) throw new Error(`${label}: movement-grid normalization did not converge`);
    seen.add(key);
    regions = union(rounded);
    if (
      regions.every((region) =>
        region.every((ring) => ring.every(([x, y]) => Number.isInteger(x) && Number.isInteger(y))),
      )
    ) {
      if (
        iteration ||
        regions.length !== rounded.length ||
        regions.some((region, index) => region.length !== rounded[index]?.length)
      )
        warnings.push(
          `${label}: normalized generated boundaries after integer-grid rounding; review geometry coverage.`,
        );
      return regions;
    }
  }
  throw new Error(`${label}: movement-grid normalization exceeded eight passes`);
}
