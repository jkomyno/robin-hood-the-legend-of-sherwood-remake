import { IDENTITY_TRANSFORM, type Level3D, type Level3DObject } from "./level3d.ts";
import {
  assetVariantId,
  type ExternalAssetSource,
  type ProjectionAssetDescriptor,
} from "./projection-assets.ts";
import { parseLevel3D, parseProjectionAssetDescriptor } from "./validation.ts";

type Descriptors = ReadonlyMap<string, ProjectionAssetDescriptor>;

function same(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a === null || b === null || typeof a !== "object" || typeof b !== "object") return false;
  if (Array.isArray(a) || Array.isArray(b))
    return (
      Array.isArray(a) &&
      Array.isArray(b) &&
      a.length === b.length &&
      a.every((value, index) => same(value, b[index]))
    );
  const x = a as Record<string, unknown>,
    y = b as Record<string, unknown>;
  const keys = Object.keys(x);
  return (
    keys.length === Object.keys(y).length &&
    keys.every((key) => Object.hasOwn(y, key) && same(x[key], y[key]))
  );
}

export function descriptorForSource(
  source: ExternalAssetSource,
  value: unknown,
): ProjectionAssetDescriptor {
  const original = parseProjectionAssetDescriptor(value);
  const variant = source.state_variant
    ? (original.state_variants ?? original.standalone_variants)?.[source.state_variant]
    : undefined;
  if (source.state_variant && !variant) throw new Error(`Missing asset variant ${source.id}`);
  if (source.state_variant && assetVariantId(original.id, source.state_variant) !== source.id)
    throw new Error(`Asset variant identity mismatch: ${source.id}`);
  if (!source.state_variant && original.id !== source.id)
    throw new Error(`Asset descriptor identity mismatch: ${source.id}`);
  return variant
    ? {
        ...original,
        id: source.id,
        name: `${original.name} — ${variant.name}`,
        model: variant.model,
        model_scene: variant.model_scene,
        parts: variant.parts ?? original.parts,
      }
    : original;
}

/** The document kind and source a placed descriptor part starts with. */
export function assetPartOrigin(
  descriptor: ProjectionAssetDescriptor,
  part: ProjectionAssetDescriptor["parts"][number],
): Pick<Level3DObject, "kind" | "source"> {
  if (part.scenery) return { kind: "scenery", source: { map: descriptor.source_map } };
  if (part.mission_profile !== undefined)
    return {
      kind: "mission",
      source: { map: descriptor.source_map, mission_profile: part.mission_profile },
    };
  return {
    kind: part.node.startsWith("terrace-") ? "terrace" : "building",
    source: {
      map: descriptor.source_map,
      obstacle: part.source_obstacle,
      ...(part.source_components ? { components: [...part.source_components] } : {}),
    },
  };
}

function defaultPart(object: Pick<Level3DObject, "node">, descriptors: Descriptors) {
  const match = /^asset:([^:]+):(.+)$/.exec(object.node);
  if (!match) return null;
  const descriptor = descriptors.get(match[1]!);
  if (!descriptor) throw new Error(`Missing pinned asset descriptor: ${match[1]}`);
  const part = descriptor.parts.find((entry) => entry.node === match[2]);
  if (!part) throw new Error(`Missing pinned asset part: ${object.node}`);
  return {
    name: part.name,
    ...assetPartOrigin(descriptor, part),
    obstacle: part.obstacle_local_game,
    transform: IDENTITY_TRANSFORM,
    hidden: part.default_hidden ? true : undefined,
  };
}

const legacyRevealKeys = new Set([
  "version",
  "source_map",
  "patches",
  "mission_patches",
  "scope",
  "coordinates",
  "visibility",
]);
const legacyPatchKeys = new Set([
  "id",
  "name",
  "state_source_game",
  "sight_before",
  "sight_after",
  "graphic",
  "associated_source_nodes",
]);

function storedMetadata(metadata: Level3D["sceneMetadata"]): Level3D["sceneMetadata"] {
  if (!metadata) return metadata;
  const { assetOrigins: _assetOrigins, ...withoutOrigins } = metadata;
  const reveal = withoutOrigins.reveal;
  if (!reveal || typeof reveal !== "object" || Array.isArray(reveal)) return withoutOrigins;
  const record = reveal as Record<string, unknown>;
  if (
    !Object.keys(record).every((key) => legacyRevealKeys.has(key)) ||
    !Array.isArray(record.patches)
  )
    return withoutOrigins;
  const patches = record.patches as unknown[];
  if (
    !patches.every(
      (patch) =>
        patch &&
        typeof patch === "object" &&
        !Array.isArray(patch) &&
        Object.keys(patch).every((key) => legacyPatchKeys.has(key)) &&
        typeof (patch as Record<string, unknown>).id === "string" &&
        typeof (patch as Record<string, unknown>).name === "string",
    )
  )
    return withoutOrigins;
  return {
    ...withoutOrigins,
    reveal: {
      patches: patches.map((patch) => ({
        id: (patch as Record<string, string>).id,
        name: (patch as Record<string, string>).name,
      })),
    },
  };
}

/** Saved maps omit descriptor defaults and obsolete reveal provenance. */
export function compactAssetInstances(document: Level3D, descriptors: Descriptors): unknown {
  parseLevel3D(document);
  return {
    ...document,
    ...(document.sceneMetadata ? { sceneMetadata: storedMetadata(document.sceneMetadata) } : {}),
    objects: document.objects.map((object) => {
      const defaults = defaultPart(object, descriptors);
      if (!defaults) return object;
      const stored: Record<string, unknown> = { ...object };
      for (const key of ["name", "kind", "source", "obstacle", "transform", "hidden"] as const) {
        if (same(object[key], defaults[key])) delete stored[key];
        else if ((key === "name" || key === "hidden") && object[key] === undefined)
          stored[key] = null;
      }
      return stored;
    }),
  };
}

/** Restore in-memory parts before normal document validation and editing. */
export function hydrateAssetInstances(value: unknown, descriptors: Descriptors): Level3D {
  if (!value || typeof value !== "object" || !Array.isArray((value as Level3D).objects))
    throw new Error("Invalid saved map document");
  const document = value as Level3D;
  const objects = document.objects.map((object) => {
    if (!object || typeof object !== "object" || typeof object.node !== "string")
      throw new Error("Invalid saved map object");
    const defaults = defaultPart(object, descriptors);
    if (!defaults) return object;
    const restored: Record<string, unknown> = { ...object };
    for (const key of ["name", "kind", "source", "obstacle", "transform", "hidden"] as const) {
      if ((key === "name" || key === "hidden") && restored[key] === null) {
        delete restored[key];
        continue;
      }
      if (restored[key] === undefined && defaults[key] !== undefined)
        restored[key] = structuredClone(defaults[key]);
    }
    return restored as unknown as Level3DObject;
  });
  return parseLevel3D({ ...document, objects });
}
