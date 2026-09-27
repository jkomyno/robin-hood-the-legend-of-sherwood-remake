/** Standalone records are storage batches, not shared rooms or asset ownership groups. */
export function recoveryDoorGroups<T>(entry: {
  Building?: { doors: T[] };
  StandaloneDoors?: { doors: T[] };
}): {
  kind: "building-interior" | "passage";
  doors: T[];
  sourceDoor?: number;
}[] {
  if (entry.Building) return [{ kind: "building-interior", doors: entry.Building.doors }];
  if (entry.StandaloneDoors)
    return entry.StandaloneDoors.doors.map((door, sourceDoor) => ({
      kind: "passage",
      doors: [door],
      sourceDoor,
    }));
  throw new Error("Unknown building record kind");
}
