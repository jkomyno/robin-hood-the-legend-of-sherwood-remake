import type { CompiledAssetGeometry } from "./asset-gameplay.ts";

/** Preserve authored query precedence while rebuilding every obstacle reference. */
export function orderSightVolumes(
  geometry: CompiledAssetGeometry,
  orders: ReadonlyMap<number, number>,
  assembled: ReadonlyMap<number, number>,
): void {
  const merged = new Map<number, number>();
  for (const [index, order] of orders) {
    const next = assembled.get(index);
    if (next === undefined) throw new Error("Missing sight order assembly reference");
    if (merged.has(next) && merged.get(next) !== order)
      throw new Error("Joined sight volumes disagree on query order");
    merged.set(next, order);
  }
  const sorted = geometry.sight_obstacles.map((shape, index) => ({ shape, index }));
  sorted.sort(
    (a, b) =>
      (merged.get(a.index) ?? Infinity) - (merged.get(b.index) ?? Infinity) || a.index - b.index,
  );
  const indices = new Map(sorted.map(({ index }, i) => [index, i]));
  const remap = (index: number) => {
    const next = indices.get(index);
    if (next === undefined)
      throw new Error("Invalid obstacle reference while ordering sight volumes");
    return next;
  };
  geometry.sight_obstacles = sorted.map((p) => p.shape);
  for (const mask of geometry.masks ?? []) mask.obstacle_indices = mask.obstacle_indices.map(remap);
  for (const transition of geometry.movement_transitions ?? []) {
    if (transition.initial_sight) transition.initial_sight = transition.initial_sight.map(remap);
    if (transition.applied_sight) transition.applied_sight = transition.applied_sight.map(remap);
  }
}
