import derby from "../assets/derby.json" with { type: "json" };
import { IDENTITY_TRANSFORM, isIdentity, type Level3D, type Level3DGroup, type Level3DObject } from "./level3d.ts";

export interface AuthoredAssetCatalog {
  map: string;
  groups: { id: string; name: string; parts: { obstacle: number; name: string }[] }[];
}

/** Upgrade only untouched generated groups; saved user edits keep their ownership. */
export function upgradeGeneratedAssetGroups(document: Level3D, catalog?: AuthoredAssetCatalog): boolean {
  if (document.groups.some(group => !/^group-\d+$/.test(group.id) || group.name || group.hidden || !isIdentity(group.transform)) ||
      document.objects.some(object => object.name || object.hidden || !isIdentity(object.transform) || object.id !== object.node)) return false;
  const groups = authoredAssetGroups(document.map, document.objects, catalog);
  if (!groups) return false;
  document.groups = groups;
  return true;
}

/** Authored ownership is independent of touching/overlapping collision volumes.
 * Explicit export metadata takes precedence; older Derby exports retain their
 * embedded catalog. Validate the complete assignment before changing any part.
 */
export function authoredAssetGroups(map: string, objects: Level3DObject[], supplied?: AuthoredAssetCatalog): Level3DGroup[] | null {
  const catalog = supplied ?? (map.toLowerCase() === derby.map.toLowerCase() ? derby : null);
  if (!catalog) return null;
  if (catalog.map.toLowerCase() !== map.toLowerCase()) throw new Error("Asset catalog belongs to a different map");
  const parts = new Map<number, { group: AuthoredAssetCatalog["groups"][number]; part: { obstacle: number; name: string } }>();
  const groupIds = new Set<string>();
  const groupNames = new Set<string>();
  for (const group of catalog.groups) {
    if (!group.id.trim() || !group.name.trim() || groupIds.has(group.id) || groupNames.has(group.name.toLowerCase()) || !group.parts.length)
      throw new Error(`${map} asset catalog has an empty or duplicate group`);
    groupIds.add(group.id);
    groupNames.add(group.name.toLowerCase());
    for (const part of group.parts) {
      if (!Number.isInteger(part.obstacle) || part.obstacle < 0 || !part.name.trim() || parts.has(part.obstacle))
        throw new Error(`${map} asset catalog has invalid or duplicate obstacle ownership`);
      parts.set(part.obstacle, { group, part });
    }
  }
  const ids = new Set(objects.map(object => object.source.obstacle));
  if (parts.size !== ids.size || objects.length !== ids.size || [...ids].some(id => !parts.has(id)) ||
      objects.some(object => object.source.map.toLowerCase() !== map.toLowerCase())) {
    throw new Error(`${map} asset catalog does not match this reconstruction's obstacle set`);
  }
  for (const object of objects) {
    const { group, part } = parts.get(object.source.obstacle)!;
    object.group = group.id;
    object.name = part.name;
  }
  return catalog.groups.map(group => ({
    id: group.id, name: group.name, transform: { ...IDENTITY_TRANSFORM },
  }));
}
