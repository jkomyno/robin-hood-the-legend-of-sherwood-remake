import type { NavigationRegion } from "./assemble-navigation-regions.ts";

/** Remove plane layers left empty by navigation joins before assigning runtime references. */
export function compactNavigationLayers(regions: NavigationRegion[]): number {
  // Zero retains ground lookup semantics even when all its authored walking space is blocked.
  const ordinary = [
    ...new Set([0, ...regions.filter((region) => !region.lift).map((region) => region.layer)]),
  ].sort((a, b) => a - b);
  const remap = new Map(ordinary.map((layer, index) => [layer, index]));
  const liftLayer = ordinary.length;
  for (const region of regions) {
    region.layer = region.lift ? liftLayer : remap.get(region.layer)!;
    for (const piece of region.pieces) piece.layer = region.layer;
  }
  regions.sort((a, b) => a.layer - b.layer);
  return liftLayer;
}
