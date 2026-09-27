import type { Polygon, MultiPolygon } from "polygon-clipping";
import { fixedClipping as clipping } from "./fixed-polygon-boolean.ts";
import earcut, { flatten } from "earcut";
import type { Point } from "./level.ts";
import { simplifyMotionRing } from "./motion-quantization.ts";

export interface ProjectionMaterialSupport {
  polygon: Point[];
  footprint?: Point[];
  defaultMaterial: number;
  materialIndices: number[];
  /** Equivalent placed definitions can have different regenerated indices. */
  materialSignature?: string;
  explicit: boolean;
  owner?: string;
  priority?: number;
  tiePriority?: number;
}
const shape = (points: Point[]): Polygon => [[...points, points[0]!]];
const area = (polygons: MultiPolygon) =>
  polygons.reduce(
    (sum, polygon) =>
      sum +
      polygon.reduce(
        (total, ring, index) =>
          total +
          ((index ? -1 : 1) *
            Math.abs(
              ring.reduce((a, p, i) => {
                const q = ring[(i + 1) % ring.length]!;
                return a + p[0] * q[1] - q[0] * p[1];
              }, 0),
            )) /
            2,
        0,
      ),
    0,
  );

/** Keep material boundaries independent of the merged navigation region. */
export function partitionProjectionMaterials(
  boundary: Point[],
  supports: ProjectionMaterialSupport[],
  warnings: string[] = [],
): ProjectionMaterialSupport[] {
  if (!supports.some((support) => support.explicit))
    return [{ polygon: boundary, defaultMaterial: 0, materialIndices: [], explicit: false }];
  const members: { support: ProjectionMaterialSupport; geometry: MultiPolygon }[] = [];
  for (const support of supports) {
    if (!support.explicit) continue;
    const coverage = support.footprint
      ? clipping.union(shape(support.polygon), shape(support.footprint))
      : shape(support.polygon);
    const geometry = clipping.intersection(shape(boundary), coverage);
    if (!geometry.length) continue;
    members.push({ support, geometry });
  }
  for (const [index, member] of members.entries())
    for (const other of members.slice(index + 1))
      if (
        !(member.support.owner && member.support.owner === other.support.owner) &&
        (member.support.priority ?? 0) === (other.support.priority ?? 0) &&
        (member.support.tiePriority ?? 0) === (other.support.tiePriority ?? 0) &&
        (member.support.defaultMaterial !== other.support.defaultMaterial ||
          (member.support.materialSignature ?? JSON.stringify(member.support.materialIndices)) !==
            (other.support.materialSignature ?? JSON.stringify(other.support.materialIndices))) &&
        area(clipping.intersection(member.geometry, other.geometry)) > 1e-7
      )
        throw new Error("Overlapping receiving surfaces have conflicting projection materials");
  members.sort(
    (a, b) =>
      (b.support.priority ?? 0) - (a.support.priority ?? 0) ||
      (b.support.tiePriority ?? 0) - (a.support.tiePriority ?? 0),
  );
  let remaining: MultiPolygon = [shape(boundary)];
  for (const member of members) {
    member.geometry = clipping.intersection(remaining, member.geometry);
    remaining = clipping.difference(remaining, member.geometry);
  }
  members.push({
    support: { polygon: boundary, defaultMaterial: 0, materialIndices: [], explicit: false },
    geometry: remaining,
  });
  return members.flatMap(({ support, geometry }) =>
    geometry.flatMap((polygon) => {
      const rings = polygon.map(simplifyMotionRing);
      if (rings[0]!.length < 3) {
        warnings.push("Receiving material partition collapsed to zero area and was omitted.");
        return [];
      }
      for (let index = rings.length - 1; index > 0; index--)
        if (rings[index]!.length < 3) {
          warnings.push(
            "Receiving material partition hole collapsed to zero area and was omitted.",
          );
          rings.splice(index, 1);
        }
      if (rings.length === 1) return [{ ...support, polygon: rings[0]! }];
      const { vertices, holes, dimensions } = flatten(rings);
      const indices = earcut(vertices, holes, dimensions);
      if (!indices.length) throw new Error("Cannot triangulate receiving material region");
      const pieces: ProjectionMaterialSupport[] = [];
      for (let i = 0; i < indices.length; i += 3)
        pieces.push({
          ...support,
          polygon: indices
            .slice(i, i + 3)
            .map((index): Point => [vertices[index * 2]!, vertices[index * 2 + 1]!]),
        });
      return pieces;
    }),
  );
}
