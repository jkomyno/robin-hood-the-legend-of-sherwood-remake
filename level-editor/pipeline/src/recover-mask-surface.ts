import { fixedClipping as clipping } from "../../shared/src/fixed-polygon-boolean.ts";
import earcut, { flatten } from "earcut";
import type { Mask, Point } from "../../shared/src/level.ts";
import type { Vec3 } from "../../shared/src/scene.ts";
import {
  rasterizeMaskGeometry,
  type MaskTriangle,
} from "../../shared/src/compile-mask-geometry.ts";
import {
  heightPlane,
  planeHeight,
  clipHeight,
  type HeightPlane,
} from "../../shared/src/gameplay-plane.ts";
import { decodeRecoveryMask, recoveryMaskRectangles } from "./recover-mask-bitmap.ts";

const closed = (points: Point[]) => [[...points, points[0]!]];

/** Lift coverage onto explicitly supplied owner surfaces. Along a projection
 * ray (0, 1, 1), the largest Z is the visible surface. Split overlapping faces
 * where their depth order changes, rather than copying coverage onto hidden
 * faces that would appear when the asset is rotated. No height is invented for
 * coverage outside the supplied mesh. Ownership must be established by caller. */
export function recoverMaskSurface(
  mask: Mask,
  surfaces: MaskTriangle[],
  localize: (point: Vec3) => Vec3,
): MaskTriangle[] {
  const faces = surfaces.flatMap((triangle) => {
    if (triangle.some((p) => p.length !== 3 || !p.every(Number.isFinite)))
      throw new Error("Invalid mask recovery surface");
    const projected: Point[] = triangle.map(([x, y, z]) => [x, y - z]);
    const [a, b, c] = projected;
    const determinant = (b![0] - a![0]) * (c![1] - a![1]) - (c![0] - a![0]) * (b![1] - a![1]);
    if (Math.abs(determinant) < 1e-8) return [];
    const plane = heightPlane(triangle.map(([x, y, z]): Vec3 => [x, y - z, z]));
    return [
      {
        projected,
        plane,
        left: Math.min(...projected.map((p) => p[0])),
        right: Math.max(...projected.map((p) => p[0])),
        top: Math.min(...projected.map((p) => p[1])),
        bottom: Math.max(...projected.map((p) => p[1])),
      },
    ];
  });
  const triangles: MaskTriangle[] = [];
  for (const rectangle of recoveryMaskRectangles(mask)) {
    const region: Point[] = [
      [rectangle.left, rectangle.top],
      [rectangle.right, rectangle.top],
      [rectangle.right, rectangle.bottom],
      [rectangle.left, rectangle.bottom],
    ];
    const candidates = faces.filter(
      (f) =>
        f.left < rectangle.right &&
        f.right > rectangle.left &&
        f.top < rectangle.bottom &&
        f.bottom > rectangle.top,
    );
    if (!candidates.length)
      throw new Error(`Mask coverage has no owner surface near ${rectangle.left},${rectangle.top}`);
    for (const [index, face] of candidates.entries()) {
      let visible = clipping.intersection(closed(region), closed(face.projected));
      if (!visible.length) continue;
      for (const [otherIndex, other] of candidates.entries()) {
        if (index === otherIndex || !visible.length) continue;
        const difference: HeightPlane = [
          other.plane[0] - face.plane[0],
          other.plane[1] - face.plane[1],
          other.plane[2] - face.plane[2],
        ];
        // Coincident faces contribute once, with stable input-order ownership.
        if (difference.every((n) => Math.abs(n) < 1e-10)) {
          if (otherIndex < index) visible = clipping.difference(visible, closed(other.projected));
          continue;
        }
        const inFront = clipHeight(other.projected, difference);
        if (inFront.length >= 3) visible = clipping.difference(visible, closed(inFront));
      }
      for (const polygon of visible) {
        const { vertices, holes, dimensions } = flatten(polygon);
        const indices = earcut(vertices, holes, dimensions);
        if (!indices.length) throw new Error("Cannot triangulate recovered mask surface");
        const point = (i: number): Vec3 => {
          const x = vertices[i * 2]!,
            y = vertices[i * 2 + 1]!;
          const z = planeHeight(face.plane, [x, y]);
          return [x, y + z, z];
        };
        for (let i = 0; i < indices.length; i += 3)
          triangles.push([point(indices[i]!), point(indices[i + 1]!), point(indices[i + 2]!)]);
      }
    }
  }
  if (!triangles.length) throw new Error("Mask coverage has no owner surface");
  // A silhouette pixel describes a sample, not an entire square of material.
  // Clip to real geometry and verify with the compiler's rasterizer, allowing
  // partial edge pixels only when the resulting binary coverage is identical.
  const remaining = decodeRecoveryMask(mask);
  for (const tile of rasterizeMaskGeometry(triangles, mask)) {
    const pixels = decodeRecoveryMask(tile);
    for (let i = 0; i < pixels.length; i++) {
      if (!pixels[i]) continue;
      const x = tile.box_top_left[0] + (i % tile.box_size[0]) - mask.box_top_left[0];
      const y = tile.box_top_left[1] + Math.floor(i / tile.box_size[0]) - mask.box_top_left[1];
      const index = y * mask.box_size[0] + x;
      if (x < 0 || y < 0 || x >= mask.box_size[0] || y >= mask.box_size[1] || !remaining[index])
        throw new Error("Recovered surface adds mask coverage");
      remaining[index] = 0;
    }
  }
  const missing = remaining.indexOf(1);
  if (missing !== -1)
    throw new Error(
      `Mask coverage has no owner surface near ${mask.box_top_left[0] + (missing % mask.box_size[0])},${mask.box_top_left[1] + Math.floor(missing / mask.box_size[0])}`,
    );
  return triangles.map(
    (triangle) =>
      triangle.map((point) => {
        const result = localize(point);
        if (result.length !== 3 || !result.every(Number.isFinite))
          throw new Error("Invalid localized mask surface");
        return result;
      }) as MaskTriangle,
  );
}
