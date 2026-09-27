import clipping, { type MultiPolygon, type Polygon } from "polygon-clipping";
import { polygonArea } from "./recover-ground-gameplay.ts";
import { recoverSurfaceSeam } from "./recovery-surface-seam.ts";

/** Only disjoint, asset-authored pieces can establish ownership of a split surface. */
export function recoverSurfaceOwners(
  regions: MultiPolygon,
  footprints: Polygon[],
  sharedCut = false,
) {
  const seam = sharedCut ? recoverSurfaceSeam(regions, footprints) : undefined;
  if (seam)
    return {
      owned: seam,
      unresolvedArea: 0,
      warnings: [
        "Surface outer boundary retained using the asset pieces' shared cut; review before publishing",
      ],
    };
  const claims = footprints.map((footprint) =>
    footprint.length ? clipping.intersection(regions, footprint) : [],
  );
  const owned = claims.map((claim, index) => {
    const others = claims.filter((_, i) => i !== index).flat();
    return others.length ? clipping.difference(claim, others) : claim;
  });
  const pieces = owned.flat();
  const assigned = pieces.length ? clipping.union(pieces) : [];
  return {
    owned,
    unresolvedArea: polygonArea(clipping.difference(regions, assigned)),
    warnings: [] as string[],
  };
}
