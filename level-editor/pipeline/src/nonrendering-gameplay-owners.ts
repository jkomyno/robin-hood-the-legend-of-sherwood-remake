export interface GameplayOwnershipCatalog {
  groups: { id: string; parts: { obstacle?: number }[] }[];
  nonrendering_sources?: { obstacle: number; owner: string }[];
  /** Offline ownership only; compiled assets retain no patch indices. */
  movement_transitions?: { patch: number; owner: string; node: string }[];
  door_sources?: { doors: number[]; owner: string; node: string; reason: string }[];
}

/** Resolve explicit authoring ownership against the assets actually pinned in the scene. */
export function nonrenderingGameplayOwners<T extends { asset: string }>(
  catalog: GameplayOwnershipCatalog,
  owners: ReadonlyMap<number, T[]>,
) {
  return (catalog.nonrendering_sources ?? []).map((source) => {
    if (!Number.isInteger(source.obstacle) || source.obstacle < 0)
      throw new Error("Invalid non-rendering gameplay source");
    const group = catalog.groups.find((g) => g.id === source.owner);
    if (!group) throw new Error(`Missing gameplay ownership group ${source.owner}`);
    const candidates = group.parts.flatMap((part) =>
      part.obstacle === undefined ? [] : (owners.get(part.obstacle) ?? []),
    );
    const direct = candidates.filter((c) => c.asset === source.owner);
    const matches = direct.length ? direct : candidates;
    const assets = [...new Set(matches.map((c) => c.asset))];
    return {
      source: source.obstacle,
      declaredOwner: source.owner,
      candidates: assets,
      owner: assets.length === 1 ? matches[0] : undefined,
    };
  });
}
