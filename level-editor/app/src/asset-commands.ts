import {
  assetNodeKey,
  assetPartOrigin,
  IDENTITY_TRANSFORM,
  parseExternalAssetSources,
  parseLevel3D,
  parseProjectionAssetDescriptor,
  type ExternalAssetSource,
  type Level3D,
  type Level3DObject,
  type ProjectionAssetDescriptor,
} from "@rle/shared";

/** A new instance shares immutable model resources but owns its document parts. */
export function insertProjectionAsset(
  document: Level3D,
  descriptor: ProjectionAssetDescriptor,
  reference: ExternalAssetSource,
  placement: [number, number, number],
) {
  parseProjectionAssetDescriptor(descriptor);
  if (descriptor.editor_usage === "map-background")
    throw new Error("Map backgrounds are part of the map and cannot be inserted as objects");
  parseExternalAssetSources([reference]);
  if (descriptor.id !== reference.id) throw new Error("Asset identity mismatch");
  if (placement.length !== 3 || placement.some((value) => !Number.isFinite(value)))
    throw new Error("Invalid asset placement");
  const existing = document.assetSources?.find((source) => source.id === reference.id);
  if (
    existing &&
    (
      [
        "descriptor",
        "model",
        "model_scene",
        "state_variant",
        "descriptor_sha256",
        "model_sha256",
      ] as const
    ).some((key) => existing[key] !== reference[key])
  )
    throw new Error("A different revision of this asset is already in the document");
  const occupied = new Set([
    ...document.groups.map((group) => group.id),
    ...document.objects.map((part) => part.id),
  ]);
  let number = 1;
  let id: string;
  do {
    id = `${descriptor.id}-instance${number++}`;
  } while (occupied.has(id) || descriptor.parts.some((part) => occupied.has(`${id}:${part.node}`)));
  const parts: Level3DObject[] = descriptor.parts.map((part) => ({
    id: `${id}:${part.node}`,
    node: assetNodeKey(descriptor.id, part.node),
    ...assetPartOrigin(descriptor, part),
    ...(part.obstacle_local_game ? { obstacle: structuredClone(part.obstacle_local_game) } : {}),
    transform: { ...IDENTITY_TRANSFORM },
    group: id,
    name: part.name,
    ...(part.default_hidden ? { hidden: true } : {}),
  }));
  const next: Level3D = {
    ...document,
    assetSources: existing
      ? document.assetSources
      : [...(document.assetSources ?? []), { ...reference }],
    groups: [
      ...document.groups,
      {
        id,
        name: descriptor.name,
        ...(descriptor.states
          ? {
              states: {
                active: descriptor.states.active,
                initial: descriptor.states.initial.map((node) => `${id}:${node}`),
                applied: descriptor.states.applied.map((node) => `${id}:${node}`),
              },
            }
          : {}),
        transform: { dx: placement[0], dy: placement[1], dz: placement[2], rot_deg: 0 },
      },
    ],
    objects: [...document.objects, ...parts],
  };
  parseLevel3D(next);
  return { document: next, selection: { kind: "group" as const, id } };
}
