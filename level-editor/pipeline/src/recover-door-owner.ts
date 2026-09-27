import type { Patch } from "@rle/shared";

/** A linked state provides ownership evidence only when all of its geometry has one owner. */
export function recoverDoorStateOwner<T extends { asset: string }>(
  doors: number[],
  patches: Pick<Patch, "door_indices" | "old_sight_obstacles" | "new_sight_obstacles">[],
  sightOwners: Map<number, T[]>,
): T | undefined {
  const linked = patches.filter((patch) => patch.door_indices.some((door) => doors.includes(door)));
  const owners: T[] = [];
  for (const patch of linked) {
    const refs = [...patch.old_sight_obstacles, ...patch.new_sight_obstacles];
    for (const ref of refs) {
      const candidates = sightOwners.get(ref) ?? [];
      if (candidates.length !== 1) return undefined;
      owners.push(candidates[0]!);
    }
  }
  const first = owners[0];
  return first && owners.every((owner) => owner.asset === first.asset) ? first : undefined;
}
