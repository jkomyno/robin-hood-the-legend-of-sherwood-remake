import type { Mask, Patch } from "../../shared/src/level.ts";
import type { AssetMovementTransition } from "../../shared/src/asset-gameplay.ts";
import { maskReferenceResolver } from "../../shared/src/mask-references.ts";

/** Bind a patch only after every referenced mask has a recovered local owner.
 * Cross-asset state changes need explicit coordination, not accidental links
 * between unrelated asset instances. No source indices survive this conversion. */
export function recoverMaskStateLinks(
  masks: readonly Mask[],
  patch: Pick<Patch, "old_masks" | "new_masks">,
  asset: string,
  owners: ReadonlyMap<number, { asset: string; id: string }>,
): Pick<AssetMovementTransition, "initialMasks" | "appliedMasks"> {
  const resolve = maskReferenceResolver(masks);
  const seen = new Set<string>();
  const local = (indices: number[]) =>
    indices.map((index) => {
      const owner = owners.get(index);
      if (!owner || !owner.id)
        throw new Error(`Mask ${index} has no recovered asset-local definition`);
      if (owner.asset !== asset)
        throw new Error(`Mask ${index} belongs to another asset: ${owner.asset}`);
      if (seen.has(owner.id)) throw new Error(`Mask state reuses local definition ${owner.id}`);
      seen.add(owner.id);
      return owner.id;
    });
  return {
    initialMasks: local(resolve(patch.old_masks, "patch.old_masks")),
    appliedMasks: local(resolve(patch.new_masks, "patch.new_masks")),
  };
}
