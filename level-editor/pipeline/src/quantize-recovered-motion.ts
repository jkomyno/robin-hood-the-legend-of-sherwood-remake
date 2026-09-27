import polygonClipping, { type MultiPolygon } from "polygon-clipping";
import { quantizeGeneratedMotionPolygon } from "../../shared/src/motion-quantization.ts";

/** Normalize crossings introduced by snapping recovered boolean geometry to the movement grid. */
export function quantizeRecoveredMotion(
  regions: MultiPolygon,
  label: string,
  warnings: string[],
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
    regions = polygonClipping.union(rounded);
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
          `${label}: normalized recovered boundaries after integer-grid rounding; review geometry coverage.`,
        );
      return regions;
    }
  }
  throw new Error(`${label}: movement-grid normalization exceeded eight passes`);
}
