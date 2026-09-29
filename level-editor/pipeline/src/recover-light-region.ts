import type { LightSector, MotionArea, Point, SightObstacle } from "../../shared/src/level.ts";
import type { Vec3 } from "../../shared/src/scene.ts";
import type { AssetLightRegion } from "../../shared/src/asset-gameplay.ts";
import { heightPlane, planeHeight, type HeightPlane } from "../../shared/src/gameplay-plane.ts";
import { partitionRecoverySurfaces } from "./recovery-surface-partition.ts";
import { fixedClipping } from "../../shared/src/fixed-polygon-boolean.ts";
import earcut, { flatten } from "earcut";

class MultipleLightPlanesError extends Error {}
class UncoveredLightGeometryError extends Error {}

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
      throw new UncoveredLightGeometryError(
        "Light region has uncovered elevated receiving geometry",
      );
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
  return recoverLightPieces(light, id, node, obstacles, motionAreas, localize, true);
}

function recoverLightPieces(
  light: LightSector,
  id: string,
  node: string,
  obstacles: SightObstacle[],
  motionAreas: MotionArea[] | undefined,
  localize: (point: Vec3) => Vec3,
  verifyIntegerContours: boolean,
  anchorOnly = false,
): AssetLightRegion[] {
  try {
    const plane = recoverLightPlane(light, obstacles, motionAreas);
    return [recoverLightRegion(light, id, node, plane, localize)];
  } catch (error) {
    if (
      !(error instanceof MultipleLightPlanesError) &&
      !(anchorOnly && error instanceof UncoveredLightGeometryError)
    )
      throw error;
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
  if (partition.ground.length && light.layer !== 0 && !anchorOnly)
    throw new Error("Multi-plane light region has uncovered elevated receiving geometry");
  const pieces = supports.map((o, i) => ({
    polygons: partition.surfaces[i]!,
    plane: heightPlane(o.points.slice(0, 3).map((p): Vec3 => [p.x, p.y - p.z_top, p.z_top])),
  }));
  if (light.layer === 0) pieces.push({ polygons: partition.ground, plane: [0, 0, 0] });
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
      if (verifyIntegerContours) {
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
    }
  return result;
}

/** Preserve one projected contour across all receiving elevations. Partitioning
 * supplies ownership footprints and interior anchors, never output contour vertices. */
export function recoverLightField(
  light: LightSector,
  id: string,
  obstacles: SightObstacle[],
  motionAreas: MotionArea[],
): { region: AssetLightRegion; footprints: Point[][] } {
  let uncovered = false;
  try {
    const plane = recoverLightPlane(light, obstacles, motionAreas);
    const region = recoverLightRegion(light, id, "$root", plane, (p) => p);
    return { region, footprints: [region.polygon.map(([x, y]): Point => [x, y])] };
  } catch (error) {
    if (
      !(error instanceof MultipleLightPlanesError) &&
      !(error instanceof UncoveredLightGeometryError)
    )
      throw error;
    uncovered = error instanceof UncoveredLightGeometryError;
  }
  // Layer-wide contours can extend beyond physical coverage. Only their anchors
  // need receiving geometry; the complete contour remains intact on the layer.
  const pieces = recoverLightPieces(
    light,
    id,
    "$root",
    obstacles,
    motionAreas,
    (p) => p,
    false,
    true,
  );
  const receivingAreas = new Map<string, { size: number; point: Vec3 }>();
  const close = (points: Point[]) => [[...points, points[0]!]];
  for (const piece of pieces) {
    const projected = piece.polygon.map(([x, y, z]): Point => [x, y - z]);
    const plane = heightPlane(piece.polygon.map(([x, y, z]): Vec3 => [x, y - z, z]));
    for (const [areaIndex, area] of motionAreas.entries()) {
      const intersections = fixedClipping.intersection(
        close(projected),
        close(area.polygon.points),
      );
      for (const polygon of intersections) {
        const { vertices, holes, dimensions } = flatten(polygon);
        const indices = earcut(vertices, holes, dimensions);
        if (!indices.length) throw new Error("Cannot locate light receiving anchor");
        for (let i = 0; i < indices.length; i += 3) {
          const triangle = indices
            .slice(i, i + 3)
            .map((j) => [vertices[j * 2]!, vertices[j * 2 + 1]!] as Point);
          const [a, b, c] = triangle;
          const size = Math.abs(
            (b![0] - a![0]) * (c![1] - a![1]) - (b![1] - a![1]) * (c![0] - a![0]),
          );
          const key = `${areaIndex}/${plane.map((n) => n.toFixed(7)).join(",")}`;
          if (size <= (receivingAreas.get(key)?.size ?? 0)) continue;
          const x = triangle.reduce((sum, p) => sum + p[0], 0) / 3;
          const y = triangle.reduce((sum, p) => sum + p[1], 0) / 3;
          const z = planeHeight(plane, [x, y]);
          receivingAreas.set(key, { size, point: [x, y + z, z] });
        }
      }
    }
  }
  const receivers = [...receivingAreas.values()].map((value) => value.point);
  if (!receivers.length) throw new Error("Light region has no receiving anchors");
  const plane = heightPlane(pieces[0]!.polygon.map(([x, y, z]): Vec3 => [x, y - z, z]));
  const region = { ...recoverLightRegion(light, id, "$root", plane, (p) => p), receivers };
  return {
    region,
    footprints: [
      ...(uncovered ? [region.polygon.map(([x, y]): Point => [x, y])] : []),
      ...pieces.map((piece) => piece.polygon.map(([x, y]): Point => [x, y])),
    ],
  };
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
