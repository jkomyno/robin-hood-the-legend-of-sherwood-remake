import type { ProjectionAssetEntry } from "@rle/shared";

export const ASSET_DRAG_TYPE = "application/x-rle-asset";

/** Published metadata takes precedence; older catalogs remain browsable. */
export function assetType(entry: ProjectionAssetEntry): string {
  if (entry.editor_usage === "map-background") return "Background";
  if (entry.asset_type) return entry.asset_type;
  const name = entry.name.toLowerCase();
  if (/tree|bush|hedge|foliage|shrub/.test(name)) return "Vegetation";
  if (/barrel|crate|timber$|well|trough|bucket|cart|tub|chopping block|hay mound/.test(name)) return "Prop";
  if (/bridge|\bgate\b|portcullis/.test(name)) return "Bridge & gate";
  if (/house|cottage|hall|keep|tower|turret|church|shed|shelter|lean-to|wing/.test(name)) return "Building";
  if (/wall|fence|palisade|curtain|archway/.test(name)) return "Wall";
  if (/terrain|terrace|ground|cliff|rock|stone|bank|field boundary/.test(name)) return "Terrain";
  return "Building";
}

export function assetTags(entry: ProjectionAssetEntry): string[] {
  return [...new Set([assetType(entry), entry.source_map, ...(entry.tags ?? []),
    ...(entry.state_variant ? [entry.state_variant] : [])])];
}

export function filterAssets(entries: ProjectionAssetEntry[], search: string, type: string, source: string) {
  const terms = search.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return entries.filter(entry => (!type || assetType(entry) === type) &&
    (!source || entry.source_map === source) &&
    terms.every(term => [entry.name, entry.id, ...assetTags(entry)].join(" ").toLowerCase().includes(term)));
}
