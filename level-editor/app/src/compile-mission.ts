import { validateMission, type Level3D, type Point } from "@rle/shared";
import type { CompiledAssetGeometry } from "../../shared/src/asset-gameplay.ts";
import { heightPlane, planeHeight } from "../../shared/src/gameplay-plane.ts";

function contains(polygon: Point[], point: Point): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i]!,
      b = polygon[j]!;
    if (
      a[1] > point[1] !== b[1] > point[1] &&
      point[0] < ((b[0] - a[0]) * (point[1] - a[1])) / (b[1] - a[1]) + a[0]
    )
      inside = !inside;
  }
  return inside;
}

/** Mission markers use game-world XYZ; exported positions use projected map pixels. */
export function compileMission(
  document: Level3D,
  bounds: [number, number, number, number],
  geometry: CompiledAssetGeometry | undefined,
  bestEffort = false,
  volumes: { footprint: Point[]; motion_blocking: boolean }[] = [],
) {
  const spawn_points: {
    position: Point;
    direction: number;
    profile: number;
    sector: number;
    layer: number;
    projection_area: number;
  }[] = [];
  const soldiers: {
    position: Point;
    direction: number;
    profile: string;
    allegiance: number;
    sector: number;
    layer: number;
    projection_area: number;
  }[] = [];
  const warnings: string[] = [];
  if (!document.mission) return { spawn_points, soldiers, warnings };
  validateMission(document.mission);
  const areas: {
    sector: number;
    layer: number;
    area: CompiledAssetGeometry["motion_data"]["layers"][number][number];
  }[] = [];
  const inactiveReceivers = new Set(
    geometry?.movement_transitions?.flatMap((transition) => transition.applied_sight ?? []) ?? [],
  );
  let sector = 0;
  geometry?.motion_data.layers.forEach((layer, index) =>
    layer.forEach((area) => {
      areas.push({ sector, layer: index, area });
      sector += 1 + area.obstacles.length;
    }),
  );
  const bind = (actor: { id: string; position: [number, number, number] }) => {
    const [x, y, z] = actor.position;
    const position: Point = [Math.round(x - bounds[0]), Math.round(y - z - bounds[1])];
    if (
      position.some((v) => v < 0 || v > 32767) ||
      position[0] >= bounds[2] ||
      position[1] >= bounds[3]
    )
      throw new Error(`Mission ${actor.id}: position is outside the export frame`);
    if (!geometry) {
      if (
        Math.abs(z) > 1 ||
        position[0] >= bounds[2] - 1 ||
        position[1] >= bounds[3] - 1 ||
        volumes.some((volume) => volume.motion_blocking && contains(volume.footprint, position))
      )
        throw new Error(`Mission ${actor.id}: position is not on the sandbox's walkable ground`);
      return { position, sector: 0, layer: 0, projection_area: 65535 };
    }
    const matches = areas.flatMap(({ sector, layer, area }) => {
      if (
        area.is_lift ||
        !contains(area.polygon.points, position) ||
        area.obstacles.some(
          (o) =>
            (o.state_id & 0x55555555) >>> 0 === o.state_id && contains(o.polygon.points, position),
        )
      )
        return [];
      const heights = geometry.sight_obstacles.flatMap((obstacle, index) => {
        if (inactiveReceivers.has(index)) return [];
        const receiver = obstacle.projection_area;
        if (
          !Array.isArray(receiver) ||
          receiver[0] !== sector ||
          receiver[1] !== layer ||
          !contains(
            obstacle.points.map((p) => [p.x, p.y - p.z_top]),
            position,
          )
        )
          return [];
        const points =
          obstacle.projection_plane ??
          obstacle.points.map((p) => [p.x, p.y, p.z_top] as [number, number, number]);
        return [
          {
            height: planeHeight(heightPlane(points.map(([a, b, c]) => [a, b - c, c])), position),
            index,
          },
        ];
      });
      const receiver = heights.find(({ height }) => Math.abs(height - z) <= 1);
      if (receiver) {
        if (receiver.index >= 65535)
          throw new Error(`Mission ${actor.id}: receiving surface exceeds the native index range`);
        return [{ sector, layer, projection_area: receiver.index }];
      }
      return !heights.length && layer === 0 && Math.abs(z) <= 1
        ? [{ sector, layer, projection_area: 65535 }]
        : [];
    });
    if (matches.length !== 1)
      throw new Error(
        `Mission ${actor.id}: position does not identify one walkable surface at height ${z}`,
      );
    return { position, ...matches[0]! };
  };
  for (const actor of [
    ...document.mission.spawnPoints.map((point) => ({ kind: "pc" as const, point })),
    ...document.mission.soldiers.map((point) => ({ kind: "soldier" as const, point })),
  ]) {
    try {
      const placement = bind(actor.point);
      if (actor.kind === "pc")
        spawn_points.push({
          ...placement,
          direction: actor.point.direction,
          profile: actor.point.profile,
        });
      else
        soldiers.push({
          ...placement,
          direction: actor.point.direction,
          profile: actor.point.profile,
          allegiance: actor.point.allegiance,
        });
    } catch (error) {
      if (!bestEffort) throw error;
      warnings.push(
        `${error instanceof Error ? error.message : String(error)}; omitted this mission marker.`,
      );
    }
  }
  return { spawn_points, soldiers, warnings };
}
