import clipping from "polygon-clipping";
import type { NavigationRegion } from "./assemble-navigation-regions.ts";
import { planeHeight, type HeightPlane } from "./gameplay-plane.ts";
import type { Point } from "./level.ts";
import type { Vec3 } from "./scene.ts";
import { lightReceiverIntersection } from "./light-receiver-segment.ts";

interface Light {
  polygon: Point[];
  plane: HeightPlane;
  receivers?: Vec3[];
  receiverSegments?: [Vec3, Vec3][];
}

/** Separate navigation regions when sharing a layer would extend an authored light. */
export function allocateLightReceivingLayers(
  regions: NavigationRegion[],
  lights: Light[],
  liftLayer: number,
  inside: (point: Point, polygon: Point[]) => boolean,
): number {
  const overlaps = (a: Point[], b: Point[]) =>
    a.some((p) => inside(p, b)) ||
    b.some((p) => inside(p, a)) ||
    clipping.intersection([a], [b]).length > 0;
  const conflicts = regions.map(() => new Set<number>());
  for (const light of lights) {
    const selected = new Set<number>();
    for (const [index, region] of regions.entries()) {
      if (region.lift) continue;
      const receives =
        light.receivers || light.receiverSegments
          ? (light.receivers ?? []).some((point) => {
              const projected: Point = [point[0], point[1] - point[2]];
              return region.pieces.some(
                (piece) =>
                  Math.abs(planeHeight(piece.plane, projected) - point[2]) < 1e-4 &&
                  inside(projected, piece.polygon),
              );
            }) ||
            (light.receiverSegments ?? []).some((segment) =>
              region.pieces.some((piece) => {
                const point = lightReceiverIntersection(segment, piece.plane);
                return (
                  point !== undefined && inside([point[0], point[1] - point[2]], piece.polygon)
                );
              }),
            )
          : region.pieces.some(
              (piece) =>
                piece.plane.every((n, i) => Math.abs(n - light.plane[i]!) < 1e-7) &&
                overlaps(piece.polygon, light.polygon),
            );
      if (receives) selected.add(index);
    }
    for (const [index, region] of regions.entries()) {
      if (region.lift || selected.has(index) || !overlaps(region.polygon, light.polygon)) continue;
      for (const receiver of selected)
        if (regions[receiver]!.layer === region.layer) {
          conflicts[index]!.add(receiver);
          conflicts[receiver]!.add(index);
        }
    }
  }
  // Keep existing layers wherever possible. Extra ordinary layers precede the
  // reserved traversal layer; sector indices are assigned after this ordering.
  let nextLayer = liftLayer;
  const oldLayers = regions.map((region) => region.layer);
  const assigned = new Set<number>();
  const alternatives = new Map<number, number[]>();
  for (const [index, region] of regions.entries()) {
    if (region.lift) continue;
    const original = oldLayers[index]!;
    const candidates = alternatives.get(original) ?? [original];
    const forbidden = new Set(
      [...conflicts[index]!]
        .filter((other) => assigned.has(other))
        .map((other) => regions[other]!.layer),
    );
    let layer = candidates.find((candidate) => !forbidden.has(candidate));
    if (layer === undefined) {
      layer = nextLayer++;
      candidates.push(layer);
    }
    alternatives.set(original, candidates);
    region.layer = layer;
    assigned.add(index);
  }
  for (const region of regions) if (region.lift) region.layer = nextLayer;
  regions.sort((a, b) => a.layer - b.layer);
  return nextLayer;
}
