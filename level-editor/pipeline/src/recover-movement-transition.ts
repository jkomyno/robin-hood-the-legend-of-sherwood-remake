import type { Patch, Point, Vec3, MotionObstacle, SightObstacle } from "@rle/shared";
import type {
  AssetMovementTransition,
  AssetWalkableSurface,
} from "../../shared/src/asset-gameplay.ts";
import { heightPlane, planeHeight, type HeightPlane } from "../../shared/src/gameplay-plane.ts";
import { partitionRecoverySurfaces } from "./recovery-surface-partition.ts";

/** One-time conversion of owned changing contours into an asset's coordinate frame. */
export function recoverMovementTransition(options: {
  id: string;
  node: string;
  patch: Pick<Patch, "active" | "definitive" | "waypoint" | "apply_sector" | "no_apply_sector">;
  initial: MotionObstacle[];
  applied: MotionObstacle[];
  initialSight: string[];
  appliedSight: string[];
  receivers: SightObstacle[];
  groundLayer: boolean;
  /** Explicit authoring plane for changing contours outside receiving coverage.
   * This places navigation geometry only; it never creates receiving surfaces. */
  uncoveredPlane?: HeightPlane;
  waypointHeight: number;
  localize: (point: Vec3) => Vec3;
}): AssetMovementTransition {
  const { id, node, patch, localize } = options;
  if (options.uncoveredPlane && !options.uncoveredPlane.every(Number.isFinite))
    throw new Error("Authored transition plane must be finite");
  const surface = (
    obstacle: MotionObstacle,
    state: string,
    index: number,
  ): AssetWalkableSurface[] => {
    const close = (points: Point[]) => [[...points, points[0]!]];
    const partition = partitionRecoverySurfaces(
      close(obstacle.polygon.points),
      [],
      options.receivers.map((receiver) => ({
        polygon: close(receiver.points.map((point): Point => [point.x, point.y - point.z_top])),
        maximumHeight: Math.max(
          ...receiver.points.map((point) => Math.max(point.z_top, point.z_bottom)),
        ),
      })),
    );
    if (partition.ground.length && !options.groundLayer && !options.uncoveredPlane)
      throw new Error("Changing obstacle has uncovered elevated receiving geometry");
    const pieces = options.receivers.flatMap((receiver, receiverIndex) => {
      const regions = partition.surfaces[receiverIndex]!;
      if (!regions.length) return [];
      // Receiving planes follow the leading vertices; trailing authored heights
      // need not lie exactly on that plane. Output contours are strictly planar.
      const plane = heightPlane(
        receiver.points
          .slice(0, 3)
          .map((point): Vec3 => [point.x, point.y - point.z_top, point.z_top]),
      );
      return regions.map((region) => ({ region, plane }));
    });
    pieces.push(
      ...partition.ground.map((region) => ({
        region,
        plane: options.uncoveredPlane ?? ([0, 0, 0] as HeightPlane),
      })),
    );
    return pieces.map(({ region, plane }, piece) => {
      const vertices = region[0]!.slice(0, -1).map(([x, y]) => {
        const z = planeHeight(plane, [x, y]);
        return localize([x, y + z, z]);
      });
      const holes = region.slice(1).map((ring) =>
        ring.slice(0, -1).map(([x, y]): Point => {
          const z = planeHeight(plane, [x, y]);
          const local = localize([x, y + z, z]);
          return [local[0], local[1]];
        }),
      );
      return {
        id: `${id}-${state}-${index}-${piece}`,
        node,
        polygon: vertices.map(([x, y]) => [x, y]),
        height: vertices.map((point) => point[2]),
        holes,
      };
    });
  };
  const atWaypointHeight = ([x, y]: Point) =>
    localize([x, y + options.waypointHeight, options.waypointHeight]);
  const contour = (points: Point[]): Point[] =>
    points.map((point) => {
      const [x, y] = atWaypointHeight(point);
      return [x, y];
    });
  return {
    id,
    node,
    active: patch.active,
    definitive: patch.definitive,
    waypoint: atWaypointHeight(patch.waypoint),
    applyPolygon: contour(patch.apply_sector.points),
    noApplyPolygon: contour(patch.no_apply_sector.points),
    initial: options.initial.flatMap((obstacle, index) => surface(obstacle, "initial", index)),
    applied: options.applied.flatMap((obstacle, index) => surface(obstacle, "applied", index)),
    initialSight: options.initialSight,
    appliedSight: options.appliedSight,
  };
}
