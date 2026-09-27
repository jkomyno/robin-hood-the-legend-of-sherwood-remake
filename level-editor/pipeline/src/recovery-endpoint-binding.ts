import type { Point, SightObstacle, Vec3 } from "@rle/shared";
import { distanceToPolygon } from "./recovery-elevation.ts";

/** Offline evidence for an endpoint whose physical support differs from its linked area. */
export interface EndpointBindingDeclaration {
  kind: "door-inside" | "door-outside" | "patch-waypoint";
  index: number;
  projection: number;
  anchor: Point;
  reason: string;
}

export function declaredEndpointBindings(
  entries: EndpointBindingDeclaration[],
  doorCount: number,
  patchCount: number,
) {
  const result = new Map<string, EndpointBindingDeclaration>();
  for (const entry of entries) {
    const count = entry.kind === "patch-waypoint" ? patchCount : doorCount;
    const key = `${entry.kind}/${entry.index}`;
    if (
      !["door-inside", "door-outside", "patch-waypoint"].includes(entry.kind) ||
      !Number.isInteger(entry.index) ||
      entry.index < 0 ||
      entry.index >= count ||
      !Number.isInteger(entry.projection) ||
      entry.projection < 0 ||
      !Array.isArray(entry.anchor) ||
      entry.anchor.length !== 2 ||
      !entry.anchor.every(Number.isFinite) ||
      typeof entry.reason !== "string" ||
      !entry.reason.trim() ||
      result.has(key)
    )
      throw new Error(`Invalid or duplicate endpoint binding ${key}`);
    result.set(key, entry);
  }
  return result;
}

export function recoverDeclaredEndpoint(
  declaration: EndpointBindingDeclaration,
  point: Point,
  layer: number,
  obstacles: SightObstacle[],
  receiverHeight: (point: Point) => number,
  physicalHeight: (obstacle: SightObstacle, point: Point) => number,
): { height: number; anchor: Vec3 } {
  const projection = obstacles[declaration.projection];
  if (
    !projection ||
    !Array.isArray(projection.projection_area) ||
    projection.projection_area[1] !== layer ||
    distanceToPolygon(
      point,
      projection.points.map((p): Point => [p.x, p.y - p.z_top]),
    ) !== 0
  )
    throw new Error("Declared endpoint projection must contain the endpoint on its layer");
  const height = physicalHeight(projection, point);
  const anchorHeight = receiverHeight(declaration.anchor);
  if (![height, anchorHeight].every(Number.isFinite))
    throw new Error("Invalid endpoint binding height");
  return {
    height,
    anchor: [declaration.anchor[0], declaration.anchor[1] + anchorHeight, anchorHeight],
  };
}
