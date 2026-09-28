import type { LightSector, MotionArea, Point, SightObstacle } from "../../shared/src/level.ts";
import type { Vec3 } from "../../shared/src/scene.ts";
import type { AssetLightRegion } from "../../shared/src/asset-gameplay.ts";
import { heightPlane, planeHeight, type HeightPlane } from "../../shared/src/gameplay-plane.ts";
import { partitionRecoverySurfaces } from "./recovery-surface-partition.ts";
import { fixedClipping } from "../../shared/src/fixed-polygon-boolean.ts";
import earcut, { flatten } from "earcut";

class MultipleLightPlanesError extends Error {}

/** Complete region coverage by one asset's parts, including interior gaps. */
export function containsLightPolygon(points: Point[], footprints: Point[][]): boolean {
  if (!footprints.length) return false;
  const polygons = footprints.map((ring) => [[...ring, ring[0]!]]);
  const coverage = fixedClipping.union(polygons[0]!, ...polygons.slice(1));
  return fixedClipping.difference([[...points, points[0]!]], coverage).length === 0;
}

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
    // A receiving-footprint notch outside navigation does not establish a
    // second plane, even on layer zero, which can also contain raised terrain.
    const uncoveredWalkable =
      !motionAreas ||
      motionAreas.some((area) => {
        const walkable = fixedClipping.difference(
          close(area.polygon.points),
          ...area.obstacles
            .filter((obstacle) => obstacle.state_id === 0)
            .map((obstacle) => close(obstacle.polygon.points)),
        );
        return fixedClipping.intersection(partition.ground, walkable).length > 0;
      });
    if (light.layer === 0) {
      if (!planes.length || uncoveredWalkable) planes.push([0, 0, 0]);
    } else if (uncoveredWalkable)
      throw new Error("Light region has uncovered elevated receiving geometry");
  }
  const plane = planes[0];
  if (!plane) throw new Error("Light region has no receiving geometry");
  if (planes.some((p) => p.some((n, i) => Math.abs(n - plane[i]!) > 1e-7)))
    throw new MultipleLightPlanesError(
      "Light region crosses receiving planes; split it during asset authoring",
    );
  return plane;
}

/** Split multi-plane lighting in projected coordinates before lifting each piece.
 * One caller-selected asset must own the entire result, not just individual pieces. */
export function recoverLightRegions(
  light: LightSector,
  id: string,
  node: string,
  obstacles: SightObstacle[],
  motionAreas: MotionArea[] | undefined,
  localize: (point: Vec3) => Vec3,
): AssetLightRegion[] {
  try {
    const plane = recoverLightPlane(light, obstacles, motionAreas);
    return [recoverLightRegion(light, id, node, plane, localize)];
  } catch (error) {
    if (!(error instanceof MultipleLightPlanesError)) throw error;
  }
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
  if (partition.ground.length && light.layer !== 0)
    throw new Error("Multi-plane light region has uncovered elevated receiving geometry");
  const pieces = supports.map((o, i) => ({
    polygons: partition.surfaces[i]!,
    plane: heightPlane(o.points.slice(0, 3).map((p): Vec3 => [p.x, p.y - p.z_top, p.z_top])),
  }));
  pieces.push({ polygons: partition.ground, plane: [0, 0, 0] });
  const result: AssetLightRegion[] = [];
  for (const { polygons, plane } of pieces)
    for (const polygon of polygons) {
      const { vertices, holes, dimensions } = flatten(polygon);
      const indices = earcut(vertices, holes, dimensions);
      if (!indices.length) throw new Error("Cannot triangulate recovered light region");
      const projectedPieces: Point[][] = [];
      for (let i = 0; i < indices.length; i += 3) {
        const points: Point[] = indices
          .slice(i, i + 3)
          .map((j) => [vertices[j * 2]!, vertices[j * 2 + 1]!]);
        projectedPieces.push(points.map(([x, y]): Point => [Math.round(x), Math.round(y)]));
        result.push(
          recoverLightRegion(
            { ...light, polygon: { points } },
            `${id}-piece-${result.length}`,
            node,
            plane,
            localize,
          ),
        );
      }
      const rounded = projectedPieces.map(close);
      const union = fixedClipping.union(rounded[0]!, ...rounded.slice(1));
      if (
        fixedClipping.difference(polygon, union).length ||
        fixedClipping.difference(union, polygon).length
      )
        throw new Error(
          "Light region changes after integer quantization; needs an authored receiving split",
        );
    }
  return result;
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
