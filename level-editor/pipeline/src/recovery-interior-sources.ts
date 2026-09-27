import type { Point, Vec3 } from "@rle/shared";
import { assembleInteriors } from "../../shared/src/assemble-interiors.ts";

export interface InteriorSourceDeclaration {
  building: number;
  reason: string;
  pieces: {
    owner: string;
    node: string;
    doors: number[];
    joins: { point: Vec3; direction: Point }[];
  }[];
}

/** Validate a one-time room partition; asset packets retain only local entrances and sockets. */
export function declaredInteriorSources<T>(
  entries: InteriorSourceDeclaration[],
  rooms: ReadonlyMap<number, number[]>,
  frames: (asset: string, node: string) => T[],
) {
  const result = new Map<number, (InteriorSourceDeclaration["pieces"][number] & { frame: T })[]>();
  const vector = (value: unknown, size: number) =>
    Array.isArray(value) &&
    value.length === size &&
    value.every((v) => typeof v === "number" && Number.isFinite(v));
  for (const entry of entries) {
    const doors = rooms.get(entry.building);
    if (
      !doors?.length ||
      result.has(entry.building) ||
      !entry.reason.trim() ||
      entry.pieces.length < 2
    )
      throw new Error(
        "Shared interior declaration needs one source room and multiple asset pieces",
      );
    const assigned = entry.pieces.flatMap((piece) => piece.doors);
    if (
      assigned.length !== doors.length ||
      new Set(assigned).size !== assigned.length ||
      assigned.some((door) => !doors.includes(door))
    )
      throw new Error("Shared interior pieces must assign every entrance exactly once");
    if (new Set(entry.pieces.map((piece) => piece.owner)).size !== entry.pieces.length)
      throw new Error("Shared interior pieces must use distinct assets");
    const pieces = entry.pieces.map((piece) => {
      const matches = frames(piece.owner, piece.node);
      if (matches.length !== 1) throw new Error("Shared interior needs one pinned frame per piece");
      if (
        !piece.joins.length ||
        piece.joins.some(
          (join) =>
            !vector(join.point, 3) ||
            !vector(join.direction, 2) ||
            Math.hypot(...join.direction) < 1e-6,
        )
      )
        throw new Error("Invalid shared interior socket");
      return { ...structuredClone(piece), frame: matches[0]! };
    });
    const joined = assembleInteriors(
      pieces.map((piece) => ({ id: piece.owner, joins: piece.joins })),
    );
    if (new Set(joined.values()).size !== 1)
      throw new Error("Shared interior authoring sockets do not connect all pieces");
    result.set(entry.building, pieces);
  }
  return result;
}
