import type { Mask, Patch } from "../../shared/src/level.ts";
import { maskReferenceResolver } from "../../shared/src/mask-references.ts";
import { recoverMaskStateLinks } from "./recover-mask-state-links.ts";

export interface RecoveredMaskTransition {
  patch: number;
  asset: string;
  transition: string;
}
export interface ReviewedMaskStateBinding {
  asset: string;
  transition: string;
  phase: "initial" | "applied";
}

/** Validate complete mask ownership before migrating any controlled geometry. */
export function reviewedMaskStateBindings(
  masks: readonly Mask[],
  patches: Pick<Patch, "old_masks" | "new_masks">[],
  recipes: { asset: string; entries: { source: number; id: string }[] }[],
  transitions: readonly RecoveredMaskTransition[],
): Map<number, ReviewedMaskStateBinding> {
  const resolve = maskReferenceResolver(masks);
  const owners = new Map<number, { asset: string; id: string }>();
  for (const recipe of recipes)
    for (const entry of recipe.entries) {
      if (
        !Number.isInteger(entry.source) ||
        entry.source < 0 ||
        !masks[entry.source] ||
        owners.has(entry.source)
      )
        throw new Error("Invalid or duplicate reviewed mask index");
      owners.set(entry.source, { asset: recipe.asset, id: entry.id });
    }
  const bindings = new Map<number, ReviewedMaskStateBinding>();
  for (const [index, patch] of patches.entries()) {
    const initial = resolve(patch.old_masks),
      applied = resolve(patch.new_masks);
    if (![...initial, ...applied].some((mask) => owners.has(mask))) continue;
    const candidates = [
      ...new Map(
        transitions
          .filter((t) => t.patch === index)
          .map((t) => [JSON.stringify([t.asset, t.transition]), t]),
      ).values(),
    ];
    if (candidates.length !== 1 || !candidates[0]!.transition)
      throw new Error(`Patch ${index} requires state recovery before its masks can migrate`);
    const owner = candidates[0]!;
    recoverMaskStateLinks(masks, patch, owner.asset, owners);
    for (const [phase, indices] of [
      ["initial", initial],
      ["applied", applied],
    ] as const)
      for (const mask of indices) {
        if (bindings.has(mask)) throw new Error(`Mask ${mask} has multiple state controllers`);
        bindings.set(mask, { asset: owner.asset, transition: owner.transition, phase });
      }
  }
  return bindings;
}
