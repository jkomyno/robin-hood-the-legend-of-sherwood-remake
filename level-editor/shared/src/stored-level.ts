/** Descriptor-backed map storage. The editor continues to work with Level3D v1 in memory. */
import {
  assetPartOrigin,
  compactAssetInstances,
  hydrateAssetInstances,
} from "./asset-instance-document.ts";
import { IDENTITY_TRANSFORM, type Level3D, type Level3DObject } from "./level3d.ts";
import type { ExternalAssetSource, ProjectionAssetDescriptor } from "./projection-assets.ts";
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
    if (key === "node" || key === "group" || key === "patches") continue;
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

function appearanceId(id: string): { asset: string; state: "base" | "initial" | "applied" } {
  const match = /^(.*)--state-(initial|applied)$/.exec(id);
  return match
    ? { asset: match[1]!, state: match[2] as "initial" | "applied" }
    : { asset: id, state: "base" };
}

function compactSources(sources: ExternalAssetSource[]): unknown[] {
  const grouped = new Map<string, ExternalAssetSource[]>();
  for (const source of sources) {
    const asset = appearanceId(source.id).asset;
    const group = grouped.get(asset) ?? [];
    group.push(source);
    grouped.set(asset, group);
  }
  return [...grouped].map(([id, group]) => {
    if (group.every((source) => appearanceId(source.id).state === "base"))
      return withoutDescriptorDefaults(group[0]!);
    const first = group[0]!;
    if (
      group.some(
        (source) =>
          source.descriptor !== first.descriptor ||
          source.descriptor_sha256 !== first.descriptor_sha256,
      )
    )
      throw new Error(`Appearance descriptors disagree: ${id}`);
    return {
      id,
      descriptor: first.descriptor,
      descriptor_sha256: first.descriptor_sha256,
      appearances: group.map((source) => ({
        state: appearanceId(source.id).state,
        model: source.model,
        model_sha256: source.model_sha256,
      })),
    };
  });
}

function withoutDescriptorDefaults<
  T extends { descriptor?: string; model_scene?: string; resources?: unknown },
>(source: T): Omit<T, "model_scene" | "resources"> {
  if (!source.descriptor) return source;
  const { model_scene: _scene, resources: _resources, ...saved } = source;
  return saved;
}

function hydrateReference<
  T extends {
    id: string;
    descriptor?: string;
    model: string;
    model_scene?: string;
    resources?: unknown;
  },
>(source: T, descriptor: ProjectionAssetDescriptor | undefined): T {
  if (!source.descriptor) return source;
  if (!descriptor) throw new Error(`Missing pinned asset descriptor: ${source.id}`);
  if (descriptor.id !== source.id)
    throw new Error(`Asset descriptor identity mismatch: ${source.id}`);
  const folder = source.descriptor.split("/").slice(0, -1).join("/");
  const model = folder ? `${folder}/${descriptor.model}` : descriptor.model;
  if (source.model !== model) throw new Error(`Asset model differs from descriptor: ${source.id}`);
  if (source.model_scene !== undefined && source.model_scene !== descriptor.model_scene)
    throw new Error(`Asset scene differs from descriptor: ${source.id}`);
  if (source.resources !== undefined && !equal(source.resources, descriptor.resources ?? []))
    throw new Error(`Asset resources differ from descriptor: ${source.id}`);
  return {
    ...source,
    ...(descriptor.model_scene ? { model_scene: descriptor.model_scene } : {}),
    ...(descriptor.resources !== undefined
      ? { resources: structuredClone(descriptor.resources) }
      : {}),
  };
}

function compactPlacement(placement: Entry): Entry {
  const assets = placement.assets as string[];
  const grouped = new Map<string, ("base" | "initial" | "applied")[]>();
  for (const id of assets) {
    const appearance = appearanceId(id);
    const states = grouped.get(appearance.asset) ?? [];
    states.push(appearance.state);
    grouped.set(appearance.asset, states);
  }
  const appearances = Object.fromEntries(
    [...grouped].filter(([, states]) => states.some((state) => state !== "base")),
  );
  return {
    ...placement,
    assets: [...grouped.keys()],
    ...(Object.keys(appearances).length ? { appearances } : {}),
  };
}

/** Expand a saved appearance bundle into the editor's pinned runtime references. */
export function expandStoredMap(value: unknown): Entry {
  const saved = record(value, "document");
  if (saved.version !== 2) return saved;
  const assetSources = (saved.assetSources as unknown[] | undefined)?.flatMap((raw) => {
    const source = record(raw, "asset source");
    if (source.appearances === undefined) {
      if (typeof source.id === "string" && appearanceId(source.id).state !== "base")
        throw new Error(`Separate appearance source is unsupported: ${source.id}`);
      return [source];
    }
    if (!Array.isArray(source.appearances) || !source.appearances.length)
      throw new Error("Invalid stored asset appearances");
    if (typeof source.id !== "string" || typeof source.descriptor !== "string")
      throw new Error("Invalid stored asset appearance bundle");
    const states = new Set<string>();
    return source.appearances.map((rawAppearance) => {
      const appearance = record(rawAppearance, "appearance");
      const state = appearance.state;
      if (!["base", "initial", "applied"].includes(state as string) || states.has(state as string))
        throw new Error(`Invalid stored asset appearance: ${source.id}`);
      states.add(state as string);
      const { state: _state, ...model } = appearance;
      return {
        id: state === "base" ? source.id : `${source.id}--state-${state}`,
        descriptor: source.descriptor,
        descriptor_sha256: source.descriptor_sha256,
        ...model,
        ...(state === "base" ? {} : { state_variant: state }),
      };
    });
  });
  const placements = (saved.placements as unknown[] | undefined)?.map((raw) => {
    const placement = record(raw, "placement");
    if (!placement.appearances) return placement;
    const appearances = record(placement.appearances, "placement appearances");
    if (!Array.isArray(placement.assets)) throw new Error("Invalid stored asset placement");
    const placementAssets = placement.assets as unknown[];
    if (Object.keys(appearances).some((id) => !placementAssets.includes(id)))
      throw new Error("Placement appearance has no asset");
    const assets = placementAssets.flatMap((id) => {
      if (typeof id !== "string") throw new Error("Invalid stored asset placement");
      const states = appearances[id];
      if (states === undefined) return [id];
      if (!Array.isArray(states) || !states.length)
        throw new Error(`Invalid placement appearances: ${id}`);
      return states.map((state) => {
        if (state !== "base" && state !== "initial" && state !== "applied")
          throw new Error(`Invalid placement appearance: ${id}`);
        return state === "base" ? id : `${id}--state-${state}`;
      });
    });
    const { appearances: _appearances, ...rest } = placement;
    return { ...rest, assets };
  });
  return {
    ...saved,
    ...(assetSources ? { assetSources } : {}),
    ...(placements ? { placements } : {}),
  };
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
  const groups = new Map(document.groups.map((group) => [group.id, group]));
  const placements: Entry[] = [];
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
      copies.push({ node: partKey(extra.node, assets), id: extra.id, ...changes(extra, defaults) });
    }
    placements.push({
      ...(group ?? {
        id,
        transform: { ...IDENTITY_TRANSFORM },
        ungrouped: true,
        ...(parts[0]!.patches ? { patches: parts[0]!.patches } : {}),
      }),
      assets,
      ...(groupMode ? { idMode } : {}),
      ...(Object.keys(overrides).length ? { parts: overrides } : {}),
      ...(removed.length ? { removed } : {}),
      ...(copies.length ? { copies } : {}),
    });
  };
  const placed = new Set<string>();
  for (const part of document.objects) {
    if (!part.group) {
      addPlacement(null, [part]);
    } else if (!placed.has(part.group)) {
      addPlacement(groups.get(part.group)!, members.get(part.group)!);
      placed.add(part.group);
    }
  }
  for (const group of document.groups) if (!placed.has(group.id)) addPlacement(group, []);
  const { objects: _objects, groups: _groups, version: _version, ...rest } = document;
  const compact = compactAssetInstances(document, descriptors) as Level3D;
  return {
    ...rest,
    assetSources: compactSources(document.assetSources),
    ...(compact.sceneMetadata ? { sceneMetadata: compact.sceneMetadata } : {}),
    version: 2,
    placements: placements.map(compactPlacement),
  };
}

/** Expand a version 2 stored map into the editor's validated in-memory document. */
export function loadAssetMap(value: unknown, descriptors: Descriptors): Level3D {
  const saved = record(value, "document");
  if (saved.version !== 2 || !Array.isArray(saved.placements))
    throw new Error("Unsupported stored asset map");
  if (Object.hasOwn(saved, "order")) throw new Error("Obsolete stored object order");
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
      patches,
      parts,
      removed,
      copies: savedCopies,
      ungrouped: _ungrouped,
      ...group
    } = placement;
    if (patches) {
      for (const [asset, rawMapping] of Object.entries(record(patches, "placement patches"))) {
        const mapping = record(rawMapping, `patches.${asset}`);
        if (mapping.state && !descriptors.get(asset)?.state_variants?.applied)
          throw new Error(`State patch requires initial/applied asset scenes: ${asset}`);
      }
    }
    if (!ungrouped)
      groups.push({
        ...group,
        ...(patches ? { patches } : {}),
      } as unknown as Level3D["groups"][number]);
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
    const placedParts = [...pending.values(), ...copies];
    if (ungrouped && patches)
      for (const part of placedParts)
        part.patches = structuredClone(patches) as Level3DObject["patches"];
    objects.push(...placedParts);
  }
  const { placements: _placements, version: _version, ...rest } = saved;
  return parseLevel3D({ ...rest, version: 1, groups, objects });
}

/** Save asset-backed documents as v2; retain v1 for reconstruction-only drafts. */
export function serializeStoredMap(document: Level3D, descriptors: Descriptors): unknown {
  const saved =
    document.assetSources?.length && document.objects.every((part) => assetId(part.node))
      ? storeAssetMap(document, descriptors)
      : compactAssetInstances(document, descriptors);
  const result = record(saved, "document");
  return {
    ...result,
    sceneAssets: document.sceneAssets.map(withoutDescriptorDefaults),
    ...(result.version === 1 && document.assetSources
      ? { assetSources: document.assetSources.map(withoutDescriptorDefaults) }
      : {}),
  };
}

/** Accept both version 2 placements and earlier full or compact part documents. */
export function parseStoredMap(value: unknown, descriptors: Descriptors): Level3D {
  const saved = expandStoredMap(value);
  const hydrated = {
    ...saved,
    ...(Array.isArray(saved.assetSources)
      ? {
          assetSources: saved.assetSources.map((raw) => {
            const source = record(raw, "asset source") as unknown as ExternalAssetSource;
            return hydrateReference(source, descriptors.get(source.id));
          }),
        }
      : {}),
    ...(Array.isArray(saved.sceneAssets)
      ? {
          sceneAssets: saved.sceneAssets.map((raw) => {
            const source = record(raw, "scene asset") as unknown as Level3D["sceneAssets"][number];
            return hydrateReference(source, descriptors.get(source.id));
          }),
        }
      : {}),
  };
  if (saved.version === 2) return loadAssetMap(hydrated, descriptors);
  if (saved.version !== 1) throw new Error("Unsupported stored map version");
  return hydrateAssetInstances(hydrated, descriptors);
}
