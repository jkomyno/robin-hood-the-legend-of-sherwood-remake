import type { EndpointBindingDeclaration } from "./recovery-endpoint-binding.ts";
import type { InteriorSourceDeclaration } from "./recovery-interior-sources.ts";
import type { SoundOwnerDeclaration } from "./recover-sound-source.ts";

export interface GameplayOwnershipCatalog {
  groups: { id: string; parts: { obstacle?: number }[] }[];
  nonrendering_sources?: { obstacle: number; owner: string }[];
  /** Restore one physical volume spanning all physical parts of a dedicated asset. */
  physical_volume_sources?: {
    obstacle: number;
    owner: string;
    node: string;
    source_sha256: string;
    model_sha256: string;
  }[];
  /** Offline ownership only; compiled assets retain no patch indices. */
  movement_transitions?: { patch: number; owner: string; node: string }[];
  door_sources?: { doors: number[]; owner: string; node: string; reason: string }[];
  endpoint_bindings?: EndpointBindingDeclaration[];
  interior_sources?: InteriorSourceDeclaration[];
  sound_sources?: SoundOwnerDeclaration[];
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
