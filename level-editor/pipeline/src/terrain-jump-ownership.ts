import type { JumpLinePair, JumpZone, Point } from "../../shared/src/level.ts";
import type { RecoveredSurface } from "./recovered-gameplay-definition.ts";
import { distanceToPolygon } from "./recovery-elevation.ts";
import type { MultiPolygon } from "polygon-clipping";
import { fixedPolygonBoolean } from "../../shared/src/fixed-polygon-boolean.ts";

/** Terrain owns a ground jump only when the gap was not transferred to a placed asset. */
export function terrainOwnsJump(
  pair: JumpLinePair,
  zones: JumpZone[],
  recoveredGroundSectors: ReadonlySet<number>,
  surfaces: RecoveredSurface[],
  transferredExclusions: MultiPolygon = [],
) {
  const lines = [pair.line1, pair.line2];
  if (
    lines.some((line) => {
      const zone = zones[line.jump_zone_index];
      return (
        !zone ||
        zone.layer !== 0 ||
        !recoveredGroundSectors.has(zone.sector) ||
        line.point_a[2] !== 0 ||
        line.point_b[2] !== 0
      );
    })
  )
    return false;
  const endpoints = lines.flatMap((line) => [
    line.point_a.slice(0, 2) as Point,
    line.point_b.slice(0, 2) as Point,
  ]);
  // The four endpoint triangles cover every direct route between the edges.
  // A movable asset owning any part of that gap prevents terrain ownership.
  if (transferredExclusions.length)
    for (let skip = 0; skip < 4; skip++) {
      const triangle = endpoints.filter((_, i) => i !== skip);
      if (fixedPolygonBoolean("intersection", [triangle], [transferredExclusions]).length)
        return false;
    }
  const free = (point: Point) =>
    surfaces.some(
      (s) =>
        s.node === "$root" &&
        s.vertices.every((p) => Math.abs(p[2]) < 1e-7) &&
        distanceToPolygon(
          point,
          s.vertices.map(([x, y]): Point => [x, y]),
        ) < 1e-7 &&
        !s.holes.some(
          (hole) =>
            distanceToPolygon(
              point,
              hole.map(([x, y]): Point => [x, y]),
            ) < 1e-7,
        ),
    );
  const centers = lines.map((line): Point => [
    (line.point_a[0] + line.point_b[0]) / 2,
    (line.point_a[1] + line.point_b[1]) / 2,
  ]);
  return (
    centers.every(free) &&
    !free([(centers[0]![0] + centers[1]![0]) / 2, (centers[0]![1] + centers[1]![1]) / 2])
  );
}
