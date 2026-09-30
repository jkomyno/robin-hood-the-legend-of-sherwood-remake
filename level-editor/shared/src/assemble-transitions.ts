import type { CompiledAssetGeometry } from "./asset-gameplay.ts";

type Transition = NonNullable<CompiledAssetGeometry["movement_transitions"]>[number];
export interface PlacedTransitionJoin {
  key: string;
  point: [number, number, number];
}

/** Join explicit contacts in world space; preview names never establish connectivity. */
export function assembleTransitions(
  transitions: Transition[],
  joins: ReadonlyMap<string, PlacedTransitionJoin>,
): Transition[] {
  const touches = (a: Transition, b: Transition) => {
    const left = joins.get(a.id);
    const right = joins.get(b.id);
    return (
      !!left &&
      !!right &&
      left.key === right.key &&
      Math.hypot(...left.point.map((n, i) => n - right.point[i]!)) <= 0.01
    );
  };
  const remaining = new Set(transitions);
  const result: Transition[] = [];
  for (const first of transitions) {
    if (!remaining.delete(first)) continue;
    const members = [first];
    for (const member of members) {
      for (const candidate of remaining) {
        if (!touches(member, candidate)) continue;
        if (!members.every((other) => touches(other, candidate)))
          throw new Error(`Ambiguous transition join near ${candidate.id}`);
        members.push(candidate);
        remaining.delete(candidate);
      }
    }
    if (members.length === 1) {
      result.push(first);
      continue;
    }
    members.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const trigger = (t: Transition) =>
      JSON.stringify([
        t.waypoint,
        t.sector,
        t.layer,
        t.active,
        t.definitive,
        t.apply_polygon,
        t.no_apply_polygon,
      ]);
    if (members.some((t) => trigger(t) !== trigger(first)))
      throw new Error(`Joined transitions need identical world triggers: ${first.id}`);
    const modes = new Set(members.flatMap((t) => (t.door_links ? [t.door_links.mode] : [])));
    if (modes.size > 1)
      throw new Error(`Joined transitions have conflicting door modes: ${first.id}`);
    const merged = structuredClone(members[0]!);
    merged.aliases = members.slice(1).map((t) => t.id);
    if (members.some((t) => t.has_appearance)) merged.has_appearance = true;
    const changes = new Map(
      members
        .flatMap((t) => t.motion_changes)
        .map((change) => [`${change.layer}/${change.sector}/${change.changing_obstacle}`, change]),
    );
    merged.motion_changes = [...changes.values()];
    for (const key of [
      "initial_sight",
      "applied_sight",
      "initial_masks",
      "applied_masks",
    ] as const) {
      const indices = [...new Set(members.flatMap((t) => t[key] ?? []))];
      if (indices.length) merged[key] = indices;
    }
    for (const [initial, applied] of [
      [merged.initial_sight, merged.applied_sight],
      [merged.initial_masks, merged.applied_masks],
    ]) {
      if (initial?.some((index) => applied?.includes(index)))
        throw new Error(`Joined transitions have conflicting state bindings: ${first.id}`);
    }
    const links = members.find((t) => t.door_links)?.door_links;
    if (links)
      merged.door_links = {
        mode: links.mode,
        indices: [...new Set(members.flatMap((t) => t.door_links?.indices ?? []))],
      };
    result.push(merged);
  }
  return result;
}
