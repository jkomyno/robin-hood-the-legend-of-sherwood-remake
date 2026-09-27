import clipping, { type MultiPolygon, type Polygon } from "polygon-clipping";

/** Partition one movement sector using projection priority, preserving source-order ties. */
export function partitionRecoverySurfaces(
  boundary: Polygon,
  holes: Polygon[],
  supports: { polygon: Polygon; maximumHeight: number }[],
) {
  const free = holes.length ? clipping.difference(boundary, ...holes) : [boundary];
  const surfaces: MultiPolygon[] = supports.map(() => []);
  let remaining = free;
  const priority = supports
    .map((support, index) => ({ ...support, index }))
    .sort((a, b) => b.maximumHeight - a.maximumHeight || a.index - b.index);
  for (const support of priority) {
    surfaces[support.index] = clipping.intersection(remaining, support.polygon);
    remaining = clipping.difference(remaining, support.polygon);
  }
  return { surfaces, ground: remaining };
}
