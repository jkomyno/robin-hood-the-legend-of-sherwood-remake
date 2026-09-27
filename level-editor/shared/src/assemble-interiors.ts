import type { Point } from "./level.ts";
import type { Vec3 } from "./scene.ts";

export interface PlacedInterior {
  id: string;
  joins: { point: Vec3; direction: Point }[];
}

/** Unmatched passage sockets leave independent rooms; ambiguous connections are authoring errors. */
export function assembleInteriors(interiors: PlacedInterior[]): Map<string, string> {
  const parent = interiors.map((_, i) => i);
  const root = (i: number): number => (parent[i] === i ? i : root(parent[i]!));
  const sockets = interiors.flatMap((interior, owner) =>
    interior.joins.map((join) => ({
      ...join,
      owner,
      direction: join.direction.map((v) => v / Math.hypot(...join.direction)) as Point,
    })),
  );
  for (const socket of sockets) {
    const matches = sockets.filter(
      (other) =>
        other !== socket &&
        Math.hypot(...socket.point.map((v, i) => v - other.point[i]!)) < 1e-4 &&
        socket.direction[0] * other.direction[0] + socket.direction[1] * other.direction[1] <
          -1 + 1e-6,
    );
    if (matches.length > 1 || matches.some((other) => other.owner === socket.owner))
      throw new Error(`Interior ${interiors[socket.owner]!.id}: ambiguous passage socket`);
    const match = matches[0];
    if (match) {
      const a = root(socket.owner),
        b = root(match.owner);
      parent[Math.max(a, b)] = Math.min(a, b);
    }
  }
  return new Map(interiors.map((interior, i) => [interior.id, interiors[root(i)]!.id]));
}
