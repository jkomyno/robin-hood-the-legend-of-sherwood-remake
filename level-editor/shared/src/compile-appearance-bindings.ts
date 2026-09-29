import type { GameplayAssetDescriptor } from "./asset-gameplay.ts";
import type { Level3D } from "./level3d.ts";

/** Bind preview names through asset-local definitions, never through source-level indices. */
export function compileAppearanceBindings(
  document: Level3D,
  assets: ReadonlyMap<string, GameplayAssetDescriptor>,
  transitions: readonly { id: string; aliases?: string[] }[] = [],
): Map<string, Record<string, string>> {
  const result = new Map<string, Record<string, string>>();
  const aliases = new Map<string, { id: string; join?: string }>();
  const canonical = new Map<string, string>();
  for (const transition of transitions) {
    for (const id of [transition.id, ...(transition.aliases ?? [])]) {
      if (canonical.has(id)) throw new Error(`Duplicate compiled transition identity: ${id}`);
      canonical.set(id, transition.id);
    }
  }
  const groups = new Map(document.groups.map((group) => [group.id, group]));
  for (const part of document.objects) {
    const group = part.group ? groups.get(part.group) : undefined;
    if (part.hidden || group?.hidden) continue;
    const asset = /^asset:([^:]+):/.exec(part.node)?.[1];
    if (!asset) continue;
    const local = new Map<string, string>();
    const joins = new Map<string, string>();
    for (const transition of assets.get(asset)?.gameplay?.movementTransitions ?? []) {
      const placed = `${part.group ?? part.id}/${asset}/${transition.id}`;
      const id = canonical.get(placed) ?? placed;
      for (const appearance of transition.appearances ?? []) {
        if (local.has(appearance))
          throw new Error(`Multiply controlled asset appearance ${appearance}`);
        local.set(appearance, id);
        if (transition.join) joins.set(appearance, transition.join.key);
      }
    }
    const preview = part.group ? group?.patches?.[asset] : part.patches?.[asset];
    for (const [appearance, alias] of Object.entries(preview ?? {})) {
      const id = local.get(appearance);
      if (!id)
        throw new Error(
          `Missing asset gameplay binding for appearance ${appearance} on ${part.id}`,
        );
      const previous = aliases.get(alias);
      const join = joins.get(appearance);
      if (previous !== undefined && previous.id !== id && (!join || previous.join !== join))
        throw new Error(`Shared appearance ${alias} needs an explicit joined gameplay transition`);
      aliases.set(alias, { id, join });
    }
    const mapping = new Map<string, string>();
    for (const [appearance, id] of local) {
      const key = preview?.[appearance] ?? appearance;
      if (mapping.has(key) && mapping.get(key) !== id)
        throw new Error(`Ambiguous placed appearance ${key}`);
      mapping.set(key, id);
    }
    result.set(part.id, Object.fromEntries(mapping));
  }
  return result;
}
