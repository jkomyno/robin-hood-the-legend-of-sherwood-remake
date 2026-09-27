import clipping, { type MultiPolygon, type Polygon } from "polygon-clipping";
import { polygonArea } from "./recover-ground-gameplay.ts";

/** Only disjoint, asset-authored pieces can establish ownership of a split surface. */
export function recoverSurfaceOwners(regions: MultiPolygon, footprints: Polygon[]) {
  const claims = footprints.map((footprint) => clipping.intersection(regions, footprint));
  const owned = claims.map((claim, index) => {
    const others = claims.filter((_, i) => i !== index).flat();
    return others.length ? clipping.difference(claim, others) : claim;
  });
  const pieces = owned.flat();
  const assigned = pieces.length ? clipping.union(pieces) : [];
  return { owned, unresolvedArea: polygonArea(clipping.difference(regions, assigned)) };
}
