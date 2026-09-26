/** Descriptor-backed map storage. The editor continues to work with Level3D v1 in memory. */
import {
  assetPartOrigin,
  compactAssetInstances,
  hydrateAssetInstances,
} from "./asset-instance-document.ts";
import { IDENTITY_TRANSFORM, type Level3D, type Level3DObject } from "./level3d.ts";
import type { ProjectionAssetDescriptor } from "./projection-assets.ts";
import { parseLevel3D } from "./validation.ts";

type Descriptors = ReadonlyMap<string, ProjectionAssetDescriptor>;
type Entry = Record<string, unknown>;

function record(value: unknown, label: string): Entry {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error(`Invalid stored map ${label}`);
  return value as Entry;
}

function equal(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (!a || !b || typeof a !== "object" || typeof b !== "object") return false;
  if (Array.isArray(a) || Array.isArray(b))
    return (
      Array.isArray(a) &&
      Array.isArray(b) &&
      a.length === b.length &&
      a.every((item, index) => equal(item, b[index]))
    );
  const x = a as Entry,
    y = b as Entry;
  return (
    Object.keys(x).length === Object.keys(y).length &&
    Object.keys(x).every((key) => Object.hasOwn(y, key) && equal(x[key], y[key]))
  );
}

function defaultObject(
  descriptor: ProjectionAssetDescriptor,
  part: ProjectionAssetDescriptor["parts"][number],
  id: string,
  group?: string,
): Level3DObject {
  return {
    id,
    node: `asset:${descriptor.id}:${part.node}`,
    ...(group ? { group } : {}),
    ...assetPartOrigin(descriptor, part),
    ...(part.obstacle_local_game ? { obstacle: structuredClone(part.obstacle_local_game) } : {}),
    transform: { ...IDENTITY_TRANSFORM },
    name: part.name,
    ...(part.default_hidden ? { hidden: true } : {}),
  };
}

function changes(actual: Level3DObject, defaults: Level3DObject): Entry {
  const result: Entry = {};
  for (const key of new Set([...Object.keys(actual), ...Object.keys(defaults)])) {
    if (key === "node" || key === "group") continue;
    const value = (actual as unknown as Entry)[key],
      baseline = (defaults as unknown as Entry)[key];
    if (equal(value, baseline)) continue;
    if (value === undefined) result[key] = null;
    else result[key] = structuredClone(value);
  }
  return result;
}

function patched(defaults: Level3DObject, override: Entry): Level3DObject {
  const result: Entry = { ...defaults };
  for (const [key, value] of Object.entries(override)) {
    if (key === "node" || key === "copy") continue;
    if (key === "group") throw new Error("Part override cannot change placement ownership");
    if (value === null) delete result[key];
    else result[key] = structuredClone(value);
  }
  return result as unknown as Level3DObject;
}

function assetId(node: string): string | null {
  return /^asset:([^:]+):.+$/.exec(node)?.[1] ?? null;
}

function partKey(node: string, assets: string[]): string {
  return assets.length === 1 ? node.split(":").slice(2).join(":") : node;
}

function expandedKey(key: string, assets: string[]): string {
  if (key.startsWith("asset:")) return key;
  if (assets.length !== 1) throw new Error(`Ambiguous asset part ${key}`);
  return `asset:${assets[0]}:${key}`;
}

/** Convert asset-backed maps to placements and sparse per-part exceptions. */
export function storeAssetMap(document: Level3D, descriptors: Descriptors): unknown {
  parseLevel3D(document);
  if (!document.assetSources?.length || document.objects.some((part) => !assetId(part.node)))
    throw new Error("Stored asset map requires descriptor-backed objects");
  const members = new Map(document.groups.map((group) => [group.id, [] as Level3DObject[]]));
  for (const part of document.objects) if (part.group) members.get(part.group)?.push(part);
  const placements: Entry[] = [];
  const generated: Level3DObject[] = [];
  const addPlacement = (group: Level3D["groups"][number] | null, parts: Level3DObject[]) => {
    const assets = [...new Set(parts.map((part) => assetId(part.node)!))];
    const id = group?.id ?? parts[0]!.id;
    const groupMode =
      !!group &&
      parts.filter((part) => part.id === `${id}:${part.node.split(":").slice(2).join(":")}`)
        .length >
        parts.filter((part) => part.id === part.node.split(":").slice(2).join(":")).length;
    const idMode = groupMode ? "group" : "node";
    const overrides: Entry = {};
    const removed: string[] = [];
    const copies: Entry[] = [];
    const remaining = [...parts];
    for (const asset of assets) {
      const descriptor = descriptors.get(asset);
      if (!descriptor) throw new Error(`Missing pinned asset descriptor: ${asset}`);
      for (const part of descriptor.parts) {
        const node = `asset:${asset}:${part.node}`;
        const defaultId = idMode === "group" ? `${id}:${part.node}` : part.node;
        const defaults = defaultObject(descriptor, part, defaultId, group?.id);
        const candidates = remaining.filter((item) => item.node === node);
        const actual = candidates.find((item) => item.id === defaultId) ?? candidates[0];
        if (!actual) {
          removed.push(partKey(node, assets));
          continue;
        }
        remaining.splice(remaining.indexOf(actual), 1);
        generated.push(actual);
        const delta = changes(actual, defaults);
        if (Object.keys(delta).length) overrides[partKey(node, assets)] = delta;
      }
    }
    for (const extra of remaining) {
      const asset = assetId(extra.node)!;
      const partNode = extra.node.split(":").slice(2).join(":");
      const descriptor = descriptors.get(asset)!;
      const definition = descriptor.parts.find((part) => part.node === partNode);
      if (!definition) throw new Error(`Missing pinned asset part: ${extra.node}`);
      const defaults = defaultObject(descriptor, definition, extra.id, group?.id);
      generated.push(extra);
      copies.push({ node: partKey(extra.node, assets), id: extra.id, ...changes(extra, defaults) });
    }
    placements.push({
      ...(group ?? { id, transform: { ...IDENTITY_TRANSFORM }, ungrouped: true }),
      assets,
      ...(groupMode ? { idMode } : {}),
      ...(Object.keys(overrides).length ? { parts: overrides } : {}),
      ...(removed.length ? { removed } : {}),
      ...(copies.length ? { copies } : {}),
    });
  };
  for (const group of document.groups) addPlacement(group, members.get(group.id) ?? []);
  for (const part of document.objects) if (!part.group) addPlacement(null, [part]);
  const positions = new Map(generated.map((part, index) => [part.id, index]));
  if (positions.size !== generated.length) throw new Error("Generated asset part IDs collide");
  const order = document.objects.map((part) => {
    const index = positions.get(part.id);
    if (index === undefined) throw new Error(`Missing generated part ${part.id}`);
    return index;
  });
  const { objects: _objects, groups: _groups, version: _version, ...rest } = document;
  const compact = compactAssetInstances(document, descriptors) as Level3D;
  return {
    ...rest,
    ...(compact.sceneMetadata ? { sceneMetadata: compact.sceneMetadata } : {}),
    version: 2,
    placements,
    ...(order.some((index, position) => index !== position) ? { order } : {}),
  };
}

/** Expand a version 2 stored map into the editor's validated in-memory document. */
export function loadAssetMap(value: unknown, descriptors: Descriptors): Level3D {
  const saved = record(value, "document");
  if (saved.version !== 2 || !Array.isArray(saved.placements))
    throw new Error("Unsupported stored asset map");
  const groups: Level3D["groups"] = [];
  const objects: Level3DObject[] = [];
  for (const raw of saved.placements) {
    const placement = record(raw, "placement");
    if (
      typeof placement.id !== "string" ||
      !Array.isArray(placement.assets) ||
      placement.assets.some((id: unknown) => typeof id !== "string")
    )
      throw new Error("Invalid stored asset placement");
    const ungrouped = placement.ungrouped === true;
    const {
      assets,
      idMode,
      parts,
      removed,
      copies: savedCopies,
      ungrouped: _ungrouped,
      ...group
    } = placement;
    if (!ungrouped) groups.push(group as unknown as Level3D["groups"][number]);
    const pending = new Map<string, Level3DObject>();
    const base = new Map<string, Level3DObject>();
    for (const id of assets as string[]) {
      const descriptor = descriptors.get(id);
      if (!descriptor) throw new Error(`Missing pinned asset descriptor: ${id}`);
      for (const part of descriptor.parts) {
        const key = `asset:${id}:${part.node}`;
        if (pending.has(key)) throw new Error(`Duplicate asset part ${key}`);
        const partId = idMode === "group" ? `${placement.id}:${part.node}` : part.node;
        const defaults = defaultObject(
          descriptor,
          part,
          partId,
          ungrouped ? undefined : placement.id,
        );
        pending.set(key, defaults);
        base.set(key, defaults);
      }
    }
    if (parts !== undefined) record(parts, "part exceptions");
    if (removed !== undefined && !Array.isArray(removed)) throw new Error("Invalid removed parts");
    if (savedCopies !== undefined && !Array.isArray(savedCopies))
      throw new Error("Invalid copied parts");
    const copies: Level3DObject[] = [];
    for (const rawKey of (removed as unknown[] | undefined) ?? []) {
      if (typeof rawKey !== "string") throw new Error("Invalid removed part");
      const key = expandedKey(rawKey, assets as string[]);
      if (!pending.delete(key)) throw new Error(`Unknown or duplicate removed part: ${key}`);
    }
    for (const [rawKey, rawOverride] of Object.entries((parts as Entry | undefined) ?? {})) {
      const key = expandedKey(rawKey, assets as string[]);
      if (!pending.has(key)) throw new Error(`Unknown or removed part exception: ${key}`);
      pending.set(key, patched(base.get(key)!, record(rawOverride, "part exception")));
    }
    for (const rawCopy of (savedCopies as unknown[] | undefined) ?? []) {
      const copy = record(rawCopy, "copied part");
      if (typeof copy.node !== "string" || typeof copy.id !== "string")
        throw new Error("Copied part requires node and ID");
      const key = expandedKey(copy.node, assets as string[]);
      const defaults = base.get(key);
      if (!defaults) throw new Error(`Unknown copied asset part: ${key}`);
      copies.push(patched(defaults, copy));
    }
    objects.push(...pending.values(), ...copies);
  }
  if (saved.order !== undefined) {
    if (
      !Array.isArray(saved.order) ||
      saved.order.length !== objects.length ||
      new Set(saved.order).size !== objects.length ||
      saved.order.some(
        (index: unknown) =>
          !Number.isInteger(index) || (index as number) < 0 || (index as number) >= objects.length,
      )
    )
      throw new Error("Invalid stored object order");
    const ordered = (saved.order as number[]).map((index) => objects[index]!);
    objects.splice(0, objects.length, ...ordered);
  }
  const { placements: _placements, order: _order, version: _version, ...rest } = saved;
  return parseLevel3D({ ...rest, version: 1, groups, objects });
}

/** Save asset-backed documents as v2; retain v1 for reconstruction-only drafts. */
export function serializeStoredMap(document: Level3D, descriptors: Descriptors): unknown {
  return document.assetSources?.length && document.objects.every((part) => assetId(part.node))
    ? storeAssetMap(document, descriptors)
    : compactAssetInstances(document, descriptors);
}

/** Accept both version 2 placements and earlier full or compact part documents. */
export function parseStoredMap(value: unknown, descriptors: Descriptors): Level3D {
  const saved = record(value, "document");
  if (saved.version === 2) return loadAssetMap(saved, descriptors);
  if (saved.version !== 1) throw new Error("Unsupported stored map version");
  return hydrateAssetInstances(saved, descriptors);
}
