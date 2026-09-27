import type { Patch, Point, SightObstacle, Vec3 } from "@rle/shared";
import { clipHeight, heightPlane } from "../../shared/src/gameplay-plane.ts";
import polygonClipping from "polygon-clipping";

/** Restrict ownership evidence to geometry above the landing and within reach of it. */
export function doorOwnershipFootprint(obstacle: SightObstacle, height: number): Point[][] {
  const plane = (key: "z_top" | "z_bottom") =>
    heightPlane(obstacle.points.slice(0, 3).map((point): Vec3 => [point.x, point.y, point[key]]));
  const top = plane("z_top"),
    bottom = plane("z_bottom");
  const footprint: Point[] = obstacle.points.map((point) => [point.x, point.y]);
  const xs = footprint.map((p) => p[0]),
    ys = footprint.map((p) => p[1]);
  const bounds: Point[] = [
    [Math.min(...xs), Math.min(...ys)],
    [Math.max(...xs), Math.min(...ys)],
    [Math.max(...xs), Math.max(...ys)],
    [Math.min(...xs), Math.max(...ys)],
  ];
  const slice = clipHeight(clipHeight(bounds, [top[0], top[1], top[2] - height - 1e-4]), [
    -bottom[0],
    -bottom[1],
    height + 24 - bottom[2],
  ]);
  if (slice.length < 3) return [];
  return polygonClipping
    .intersection([[...footprint, footprint[0]!]], [[...slice, slice[0]!]])
    .map((polygon) => polygon[0]!.slice(0, -1));
}

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
