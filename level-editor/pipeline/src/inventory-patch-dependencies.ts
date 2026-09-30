import type { Patch, SightObstacle } from "../../shared/src/level.ts";
type PatchLinks = Pick<
  Patch,
  "old_sight_obstacles" | "new_sight_obstacles" | "old_masks" | "new_masks" | "door_indices"
>;

/** One-time authoring audit. Shared references are dependencies to review, not
 * permission to assign distant geometry to one asset or to copy mission actors. */
export function inventoryPatchDependencies(
  entries: { id: string; patch: PatchLinks }[],
  obstacles: SightObstacle[],
) {
  const identities = new Set<string>();
  const targets = new Map<
    string,
    {
      kind: "sight" | "mask" | "door";
      reference: number | number[];
      uses: { patch: string; role: string }[];
    }
  >();
  const projectionChanges: { patch: string; role: string; obstacle: number }[] = [];
  const add = (
    kind: "sight" | "mask" | "door",
    reference: number | number[],
    patch: string,
    role: string,
  ) => {
    if (
      (Array.isArray(reference) ? reference : [reference]).some(
        (n) => !Number.isInteger(n) || n < 0,
      )
    )
      throw new Error(`Invalid ${kind} reference on ${patch}`);
    const key = `${kind}:${JSON.stringify(reference)}`;
    const target = targets.get(key) ?? { kind, reference, uses: [] };
    target.uses.push({ patch, role });
    targets.set(key, target);
  };
  for (const { id, patch } of entries) {
    if (!id || identities.has(id)) throw new Error("Patch audit needs unique nonempty identities");
    identities.add(id);
    for (const [role, indices] of [
      ["initial", patch.old_sight_obstacles],
      ["applied", patch.new_sight_obstacles],
    ] as const)
      for (const index of indices) {
        const obstacle = obstacles[index];
        if (!obstacle) throw new Error(`${id}: missing sight obstacle ${index}`);
        add("sight", index, id, role);
        if (Array.isArray(obstacle.projection_area))
          projectionChanges.push({ patch: id, role, obstacle: index });
      }
    for (const [role, masks] of [
      ["initial", patch.old_masks],
      ["applied", patch.new_masks],
    ] as const)
      for (const mask of masks) add("mask", [mask.layer, mask.index], id, role);
    for (const index of patch.door_indices) add("door", index, id, "binding");
  }
  return {
    patches: entries.length,
    projectionChanges,
    shared: [...targets.values()].filter(
      (target) => new Set(target.uses.map((use) => use.patch)).size > 1,
    ),
  };
}
