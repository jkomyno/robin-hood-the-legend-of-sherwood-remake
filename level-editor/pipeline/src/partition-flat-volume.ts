import type { Point, SightObstacle } from "@rle/shared";
import { fixedClipping } from "../../shared/src/fixed-polygon-boolean.ts";
import type { MultiPolygon } from "polygon-clipping";

export type VolumeVertex = number | { edge: number; fraction: number };

/** Offline authoring: partition a flat volume along explicitly reviewed asset seams. */
export function partitionFlatVolume(
  source: SightObstacle,
  partitions: VolumeVertex[][],
): SightObstacle[] {
  const first = source.points[0];
  if (
    !first ||
    source.points.length < 3 ||
    source.points.some(
      (p) =>
        ![p.x, p.y, p.z_bottom, p.z_top].every(Number.isFinite) ||
        p.z_bottom !== first.z_bottom ||
        p.z_top !== first.z_top,
    )
  )
    throw new Error("Partition recovery requires constant finite bottom and top heights");
  if (source.projection_area != null || source.projection_plane || source.material_indices.length)
    throw new Error("Receiving geometry and materials require separate partition authoring");
  const vertex = (reference: VolumeVertex) => {
    const index = typeof reference === "number" ? reference : reference.edge;
    const a = source.points[index];
    if (!Number.isInteger(index) || !a) throw new Error("Invalid partition vertex");
    if (typeof reference === "number") return { ...a };
    const t = reference.fraction;
    if (!Number.isFinite(t) || t <= 0 || t >= 1) throw new Error("Invalid edge fraction");
    const b = source.points[(index + 1) % source.points.length]!;
    return { ...a, x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
  };
  const pieces = partitions.map((partition) => ({
    ...structuredClone(source),
    points: partition.map(vertex),
  }));
  if (pieces.length < 2 || pieces.some((piece) => piece.points.length < 3))
    throw new Error("At least two nonempty volume partitions are required");
  const ring = (shape: SightObstacle): Point[][] => [shape.points.map((p) => [p.x, p.y])];
  const area = (polygons: MultiPolygon) =>
    polygons.reduce(
      (total, polygon) =>
        total +
        polygon.reduce(
          (sum, ring, i) =>
            sum +
            ((i ? -1 : 1) *
              Math.abs(
                ring.reduce((sum, p, j) => {
                  const q = ring[(j + 1) % ring.length]!;
                  return sum + p[0] * q[1] - q[0] * p[1];
                }, 0),
              )) /
              2,
          0,
        ),
      0,
    );
  const polygons = pieces.map(ring);
  const union = fixedClipping.union(polygons[0]!, ...polygons.slice(1));
  // Fixed-point intersection rounding may leave subpixel slivers along inserted seams.
  const tolerance = 0.001;
  if (area(fixedClipping.xor(ring(source), union)) > tolerance)
    throw new Error("Volume partitions change the outer footprint");
  for (let i = 0; i < polygons.length; i++) {
    if (area(fixedClipping.union(polygons[i]!)) <= tolerance)
      throw new Error("Degenerate volume partition");
    for (let j = 0; j < i; j++)
      if (area(fixedClipping.intersection(polygons[i]!, polygons[j]!)) > tolerance)
        throw new Error("Volume partitions overlap");
  }
  return pieces;
}
