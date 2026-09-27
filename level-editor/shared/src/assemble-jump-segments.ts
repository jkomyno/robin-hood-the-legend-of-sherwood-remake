import type { Vec3 } from "./scene.ts";

export interface PlacedJumpSegment {
  id: string;
  long: boolean;
  join: Vec3;
  edge: { zone: string; a: Vec3; b: Vec3 };
}

/** Explicit sockets pair independently movable edges without retaining asset or scene links. */
export function assembleJumpSegments(segments: PlacedJumpSegment[]) {
  const consumed = new Set<PlacedJumpSegment>();
  const pairs: { id: string; long: boolean; edges: PlacedJumpSegment["edge"][] }[] = [];
  for (const segment of segments) {
    if (consumed.has(segment)) continue;
    const matches = segments.filter(
      (other) =>
        other !== segment && Math.hypot(...segment.join.map((n, i) => n - other.join[i]!)) < 1e-4,
    );
    if (matches.length !== 1 || consumed.has(matches[0]!))
      throw new Error(`Jump ${segment.id}: join must match exactly one complementary edge`);
    const other = matches[0]!;
    if (segment.long !== other.long)
      throw new Error(`Jump ${segment.id}: paired long-jump rules disagree`);
    if (segment.edge.zone === other.edge.zone)
      throw new Error(`Jump ${segment.id}: both edges use the same landing zone`);
    consumed.add(segment);
    consumed.add(other);
    pairs.push({ id: segment.id, long: segment.long, edges: [segment.edge, other.edge] });
  }
  return pairs;
}
