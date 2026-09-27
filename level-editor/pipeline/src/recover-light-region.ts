import type { LightSector, MotionArea, Point, SightObstacle } from "../../shared/src/level.ts";
import type { Vec3 } from "../../shared/src/scene.ts";
import type { AssetLightRegion } from "../../shared/src/asset-gameplay.ts";
import { heightPlane, planeHeight, type HeightPlane } from "../../shared/src/gameplay-plane.ts";
import { partitionRecoverySurfaces } from "./recovery-surface-partition.ts";
import { fixedClipping } from "../../shared/src/fixed-polygon-boolean.ts";

/** Preserve projection priority and reject regions that need multiple receiving planes. */
export function recoverLightPlane(
  light: LightSector,
  obstacles: SightObstacle[],
  motionAreas?: MotionArea[],
): HeightPlane {
  const supports = obstacles.filter(
    (o) => Array.isArray(o.projection_area) && o.projection_area[1] === light.layer,
  );
  const close = (p: Point[]) => [[...p, p[0]!]];
  const partition = partitionRecoverySurfaces(
    close(light.polygon.points),
    [],
    supports.map((o) => ({
      polygon: close(o.points.map((p): Point => [p.x, p.y - p.z_top])),
      maximumHeight: Math.max(...o.points.map((p) => Math.max(p.z_top, p.z_bottom))),
    })),
  );
  const planes = supports.flatMap((o, i) =>
    partition.surfaces[i]!.length
      ? [heightPlane(o.points.slice(0, 3).map((p): Vec3 => [p.x, p.y - p.z_top, p.z_top]))]
      : [],
  );
  if (partition.ground.length) {
    if (light.layer === 0) planes.push([0, 0, 0]);
    else {
      // A light contour can extend outside navigation. Its single receiving
      // plane continues there; never extrapolate over potentially walkable gaps.
      if (
        !motionAreas ||
        motionAreas.some((area) => {
          const walkable = fixedClipping.difference(
            close(area.polygon.points),
            ...area.obstacles
              .filter((obstacle) => obstacle.state_id === 0)
              .map((obstacle) => close(obstacle.polygon.points)),
          );
          return fixedClipping.intersection(partition.ground, walkable).length > 0;
        })
      )
        throw new Error("Light region has uncovered elevated receiving geometry");
    }
  }
  const plane = planes[0];
  if (!plane) throw new Error("Light region has no receiving geometry");
  if (planes.some((p) => p.some((n, i) => Math.abs(n - plane[i]!) > 1e-7)))
    throw new Error("Light region crosses receiving planes; split it during asset authoring");
  return plane;
}

/** Convert projected contours to an explicit owner's local world coordinates. */
export function recoverLightRegion(
  light: LightSector,
  id: string,
  node: string,
  plane: HeightPlane,
  localize: (point: Vec3) => Vec3,
): AssetLightRegion {
  return {
    id,
    node,
    ambiences: light.ambience,
    polygon: light.polygon.points.map(([x, y]) => {
      const z = planeHeight(plane, [x, y]);
      return localize([x, y + z, z]);
    }),
  };
}
