import derby from "../assets/derby.json" with { type: "json" };
import { IDENTITY_TRANSFORM, isIdentity, type Level3D, type Level3DGroup, type Level3DObject } from "./level3d.ts";
import type { SightObstacle } from "./level.ts";
import { parseLevel3D } from "./validation.ts";

export type AuthoredAssetPart = { name: string } & (
  { obstacle: number; node?: never; mission_profile?: never; obstacle_local_game?: never } |
  { obstacle?: never; node: string; mission_profile: string; obstacle_local_game?: SightObstacle }
);

export interface AuthoredAssetCatalog {
  map: string;
  groups: { id: string; name: string; parts: AuthoredAssetPart[] }[];
}

/** Publication-only migration: append exactly the reviewed supplemental nodes.
 * Never invoked while opening saved documents, so deleted parts stay deleted.
 * Catalog footprints must be in the document's world/game coordinate frame.
 */
export function appendSupplementalMissionParts(document: Level3D, catalog: AuthoredAssetCatalog, allowedNodes: string[]): Level3D {
  parseLevel3D(document);
  if (catalog.map.toLowerCase() !== document.map.toLowerCase()) throw new Error("Supplemental catalog belongs to a different map");
  const allowed = new Set(allowedNodes);
  if (allowed.size !== allowedNodes.length || allowedNodes.some(node => !/^mission-[a-zA-Z0-9_-]+$/.test(node)))
    throw new Error("Invalid supplemental node allowlist");
  const additions: Level3DObject[] = [];
  const groups: Level3DGroup[] = [];
  const found = new Set<string>();
  for (const group of catalog.groups) for (const part of group.parts) {
    if (part.mission_profile === undefined || !allowed.has(part.node)) continue;
    if (found.has(part.node) || document.objects.some(object => object.node === part.node || object.id === part.node))
      throw new Error(`Supplemental node already exists or has duplicate ownership: ${part.node}`);
    if (part.obstacle !== undefined || !part.obstacle_local_game || !part.name.trim() || !group.name.trim() || !group.id.trim())
      throw new Error(`Invalid supplemental part metadata: ${part.node}`);
    found.add(part.node);
    if (!document.groups.some(existing => existing.id === group.id) && !groups.some(existing => existing.id === group.id))
      groups.push({ id: group.id, name: group.name, transform: { ...IDENTITY_TRANSFORM } });
    additions.push({ id: part.node, node: part.node, kind: "mission", group: group.id, name: part.name,
      source: { map: document.map, mission_profile: part.mission_profile },
      obstacle: structuredClone(part.obstacle_local_game), transform: { ...IDENTITY_TRANSFORM } });
  }
  if (found.size !== allowed.size) throw new Error("Supplemental node allowlist does not match the catalog");
  const next = { ...document, groups: [...document.groups, ...groups], objects: [...document.objects, ...additions] };
  parseLevel3D(next);
  return next;
}

/** An older reconstruction can predate explicit supplemental mission previews.
 * Only the embedded fallback catalog may omit those absent supplemental nodes;
 * an explicit exported catalog must still match every part exactly.
 */
export function catalogForLegacyReconstruction(catalog: AuthoredAssetCatalog, objects: Level3DObject[]): AuthoredAssetCatalog {
  const nodes = new Set(objects.map(object => object.node));
  return { ...catalog, groups: catalog.groups.flatMap(group => {
    if (!group.parts.length || !group.id.trim() || !group.name.trim()) return [group];
    const parts = group.parts.filter(part => !(part.obstacle === undefined &&
      !!part.name.trim() &&
      typeof part.mission_profile === "string" && part.mission_profile.trim() &&
      typeof part.node === "string" && /^mission-[a-zA-Z0-9_-]+$/.test(part.node) && !nodes.has(part.node)));
    return parts.length ? [{ ...group, parts }] : [];
  }) };
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
  const catalog: AuthoredAssetCatalog | null = supplied ?? (map.toLowerCase() === derby.map.toLowerCase() ? catalogForLegacyReconstruction(derby, objects) : null);
  if (!catalog) return null;
  if (catalog.map.toLowerCase() !== map.toLowerCase()) throw new Error("Asset catalog belongs to a different map");
  const parts = new Map<string, { group: AuthoredAssetCatalog["groups"][number]; part: AuthoredAssetPart }>();
  const groupIds = new Set<string>();
  const groupNames = new Set<string>();
  for (const group of catalog.groups) {
    if (!group.id.trim() || !group.name.trim() || groupIds.has(group.id) || groupNames.has(group.name.toLowerCase()) || !group.parts.length)
      throw new Error(`${map} asset catalog has an empty or duplicate group`);
    groupIds.add(group.id);
    groupNames.add(group.name.toLowerCase());
    for (const part of group.parts) {
      const key = part.mission_profile !== undefined ? part.node : `obstacle:${part.obstacle}`;
      const valid = part.mission_profile !== undefined ?
        part.obstacle === undefined && /^mission-[a-zA-Z0-9_-]+$/.test(part.node) && !!part.mission_profile.trim() :
        Number.isInteger(part.obstacle) && part.obstacle >= 0;
      if (!valid || !part.name.trim() || parts.has(key))
        throw new Error(`${map} asset catalog has invalid or duplicate obstacle ownership`);
      parts.set(key, { group, part });
    }
  }
  const objectKey = (object: Level3DObject) => object.kind === "mission" ? object.node : `obstacle:${object.source.obstacle}`;
  const ids = new Set(objects.map(objectKey));
  if (parts.size !== ids.size || objects.length !== ids.size || [...ids].some(id => !parts.has(id)) ||
      objects.some(object => object.source.map.toLowerCase() !== map.toLowerCase() ||
        object.source.mission_profile !== parts.get(objectKey(object))?.part.mission_profile)) {
    throw new Error(`${map} asset catalog does not match this reconstruction's obstacle set`);
  }
  for (const object of objects) {
    const { group, part } = parts.get(objectKey(object))!;
    object.group = group.id;
    object.name = part.name;
  }
  return catalog.groups.map(group => ({
    id: group.id, name: group.name, transform: { ...IDENTITY_TRANSFORM },
  }));
}
