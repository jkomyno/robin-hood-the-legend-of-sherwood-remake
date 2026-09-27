/** Offline comparison of non-lift doors, room membership and door-linked patch rules. */
import fs from "node:fs/promises";
import { pathToFileURL } from "node:url";
import type { Patch, Point } from "@rle/shared";
import type { CompiledAssetGeometry } from "../../shared/src/asset-gameplay.ts";
import { canonical } from "./bundle-asset-states.ts";

type Door = CompiledAssetGeometry["doors"][number];
export interface SourceDoorGeometry {
  buildings: ({ Building: { doors: Door[] } } | { StandaloneDoors: { doors: Door[] } })[];
  patches: Pick<
    Patch,
    | "active"
    | "definitive"
    | "waypoint"
    | "apply_sector"
    | "no_apply_sector"
    | "door_triggered"
    | "triggers_door"
    | "door_indices"
  >[];
}

function ring(points: Point[]) {
  if (!points.length) return "[]";
  const variants: string[] = [];
  for (const order of [points, [...points].reverse()])
    for (let i = 0; i < order.length; i++)
      variants.push(canonical([...order.slice(i), ...order.slice(0, i)]));
  return variants.sort()[0]!;
}

function doorKey(door: Door) {
  // Sector/layer identities are regenerated; endpoint geometry and behavior remain comparable.
  const {
    sector_in: _si,
    sector_out: _so,
    layer_in: _li,
    layer_out: _lo,
    door_sector,
    ...rules
  } = door;
  return canonical({ ...rules, polygon: ring(door_sector.points) });
}

function difference(source: string[], compiled: string[]) {
  const remaining = [...compiled];
  const missing = source.filter((key) => {
    const index = remaining.indexOf(key);
    if (index < 0) return true;
    remaining.splice(index, 1);
    return false;
  });
  return {
    source: source.length,
    compiled: compiled.length,
    missing: missing.length,
    extra: remaining.length,
  };
}

function bindingKey(
  doors: Door[],
  indices: number[],
  mode: string,
  active: boolean,
  definitive: boolean,
  waypoint: Point,
  apply: Point[],
  noApply: Point[],
) {
  return canonical({
    mode,
    active,
    definitive,
    waypoint,
    apply: ring(apply),
    noApply: ring(noApply),
    doors: indices
      .map((index) => {
        if (!Number.isInteger(index) || !doors[index])
          throw new Error(`Invalid door binding ${index}`);
        return doorKey(doors[index]);
      })
      .sort(),
  });
}

export function compareDoorGeometry(source: SourceDoorGeometry, compiled: CompiledAssetGeometry) {
  const sourceDoors = source.buildings.flatMap((entry) =>
    "Building" in entry ? entry.Building.doors : entry.StandaloneDoors.doors,
  );
  const compiledDoors = [
    ...(compiled.buildings ?? []).flatMap((entry) => entry.Building.doors),
    ...compiled.doors,
  ];
  const sourceRooms = source.buildings.flatMap((entry) =>
    "Building" in entry ? [canonical(entry.Building.doors.map(doorKey).sort())] : [],
  );
  const compiledRooms = (compiled.buildings ?? []).map((entry) =>
    canonical(entry.Building.doors.map(doorKey).sort()),
  );
  const sourceBindings = source.patches
    .filter((patch) => patch.door_indices.length)
    .map((patch) => {
      if (!patch.door_triggered && !patch.triggers_door)
        throw new Error("Door patch has no binding direction");
      return bindingKey(
        sourceDoors,
        patch.door_indices,
        patch.door_triggered ? "trigger-transition" : "swap-rights",
        patch.active,
        patch.definitive,
        patch.waypoint,
        patch.apply_sector.points,
        patch.no_apply_sector.points,
      );
    });
  const compiledBindings = (compiled.movement_transitions ?? []).flatMap((transition) =>
    transition.door_links
      ? [
          bindingKey(
            compiledDoors,
            transition.door_links.indices,
            transition.door_links.mode,
            transition.active,
            transition.definitive,
            transition.waypoint,
            transition.apply_polygon.points,
            transition.no_apply_polygon.points,
          ),
        ]
      : [],
  );
  const doors = difference(sourceDoors.map(doorKey), compiledDoors.map(doorKey));
  const rooms = difference(sourceRooms, compiledRooms);
  const bindings = difference(sourceBindings, compiledBindings);
  return {
    scope: "non-lift-door-geometry-room-membership-and-bindings",
    doors,
    rooms,
    bindings,
    equivalent: [doors, rooms, bindings].every((result) => !result.missing && !result.extra),
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [source, compiled] = process.argv.slice(2);
  if (!source || !compiled)
    throw new Error("Usage: compare-door-geometry.ts SOURCE_JSON COMPILED_LEVEL_JSON");
  const result = compareDoorGeometry(
    JSON.parse(await fs.readFile(source, "utf8")),
    JSON.parse(await fs.readFile(compiled, "utf8")).asset_geometry,
  );
  console.log(JSON.stringify(result, null, 2));
  if (!result.equivalent) process.exitCode = 1;
}
