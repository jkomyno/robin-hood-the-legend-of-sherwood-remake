import type { CompiledAssetGeometry } from "./asset-gameplay.ts";
import type { SightObstacle } from "./level.ts";
import type { Vec3 } from "./scene.ts";
import polygonClipping from "polygon-clipping";

export interface PlacedSightJoin {
  index: number;
  edge: [Vec3, Vec3];
}

export interface PlacedSightCap {
  index: number;
  cap: "top" | "bottom";
}

/** Remove explicitly authored internal faces only when their placed seams match. */
export function assembleSightVolumes(
  geometry: CompiledAssetGeometry,
  joins: PlacedSightJoin[],
  caps: PlacedSightCap[] = [],
): void {
  if (!joins.length && !caps.length) return;
  const sight = geometry.sight_obstacles;
  const near = (a: Vec3, b: Vec3) => Math.hypot(...a.map((v, i) => v - b[i]!)) < 1e-5;
  const parent = sight.map((_, i) => i);
  const root = (i: number): number => (parent[i] === i ? i : root(parent[i]!));
  const referenced = new Set([
    ...(geometry.masks ?? []).flatMap((m) => m.obstacle_indices),
    ...(geometry.movement_transitions ?? []).flatMap((t) => [
      ...(t.initial_sight ?? []),
      ...(t.applied_sight ?? []),
    ]),
  ]);
  const firstPoint = (shape: SightObstacle) => shape.points[0]!;
  for (const join of [...joins, ...caps]) {
    const shape = sight[join.index];
    if (
      !shape ||
      referenced.has(join.index) ||
      shape.projection_area !== null ||
      shape.material_indices.length ||
      shape.projection_plane
    )
      throw new Error(
        "Sight seams require unlinked static volumes without receiving geometry or materials",
      );
    const first = firstPoint(shape);
    if (
      shape.points.some(
        (p) =>
          Math.fround(p.z_bottom) !== Math.fround(first.z_bottom) ||
          Math.fround(p.z_top) !== Math.fround(first.z_top),
      )
    )
      throw new Error("Sight seams require flat top and bottom planes");
    if (
      "edge" in join &&
      !shape.points.some((p, i) => {
        const q = shape.points[(i + 1) % shape.points.length]!;
        return (
          near([p.x, p.y, p.z_bottom], join.edge[0]) && near([q.x, q.y, q.z_bottom], join.edge[1])
        );
      })
    )
      throw new Error("Sight seam must follow a complete directed volume edge");
  }
  const sameFootprint = (a: SightObstacle, b: SightObstacle) =>
    a.points.length === b.points.length &&
    b.points.some((_, start) =>
      [1, -1].some((direction) =>
        a.points.every((p, i) => {
          const q = b.points[(start + direction * i + b.points.length) % b.points.length]!;
          return Math.fround(p.x) === Math.fround(q.x) && Math.fround(p.y) === Math.fround(q.y);
        }),
      ),
    );
  const capHeight = (cap: PlacedSightCap) =>
    Math.fround(firstPoint(sight[cap.index]!)[cap.cap === "top" ? "z_top" : "z_bottom"]);
  const flags = ["opaque", "solid", "mouse", "show_shadow_polygon", "default_material"] as const;
  for (const [i, a] of caps.entries()) {
    const shape = sight[a.index]!;
    if (joins.some((join) => join.index === a.index))
      throw new Error("A sight volume cannot combine edge and cap seams");
    if (a.cap !== "top" && a.cap !== "bottom") throw new Error("Invalid sight cap");
    if (Math.fround(firstPoint(shape).z_top) <= Math.fround(firstPoint(shape).z_bottom))
      throw new Error("Sight cap requires positive volume thickness");
    if (caps.some((b, j) => j !== i && b.index === a.index && b.cap === a.cap))
      throw new Error("Duplicate sight cap");
    const matches = caps.filter(
      (b) =>
        b.index !== a.index &&
        b.cap !== a.cap &&
        capHeight(a) === capHeight(b) &&
        sameFootprint(shape, sight[b.index]!),
    );
    if (matches.length > 1) throw new Error("Ambiguous sight cap across overlapping placements");
    const b = matches[0];
    if (!b) continue;
    if (flags.some((key) => shape[key] !== sight[b.index]![key]))
      throw new Error("Matching sight caps disagree on physical flags");
    parent[root(b.index)] = root(a.index);
  }
  for (const [i, a] of joins.entries()) {
    const matches = joins.flatMap((b, j) =>
      i !== j && near(a.edge[0], b.edge[1]) && near(a.edge[1], b.edge[0]) ? [b] : [],
    );
    if (matches.length > 1) throw new Error("Ambiguous sight seam across overlapping placements");
    const b = matches[0];
    if (!b) continue;
    if (a.index === b.index) throw new Error("Sight seam cannot join a volume to itself");
    const sa = sight[a.index]!,
      sb = sight[b.index]!;
    if (
      (["opaque", "solid", "mouse", "show_shadow_polygon", "default_material"] as const).some(
        (k) => sa[k] !== sb[k],
      ) ||
      Math.fround(firstPoint(sa).z_bottom) !== Math.fround(firstPoint(sb).z_bottom) ||
      Math.fround(firstPoint(sa).z_top) !== Math.fround(firstPoint(sb).z_top)
    )
      throw new Error("Matching sight seams disagree on physical flags or heights");
    parent[root(b.index)] = root(a.index);
  }
  const groups = new Map<number, number[]>();
  for (let i = 0; i < sight.length; i++) {
    const key = root(i);
    const group = groups.get(key) ?? [];
    group.push(i);
    groups.set(key, group);
  }
  const indices = new Map<number, number>();
  const assembled: SightObstacle[] = [];
  for (const group of groups.values()) {
    const shape = sight[group[0]!]!;
    for (const index of group) indices.set(index, assembled.length);
    if (group.length === 1) {
      assembled.push(shape);
      continue;
    }
    if (caps.some((cap) => group.includes(cap.index))) {
      const stack = group
        .map((index) => sight[index]!)
        .sort((a, b) => firstPoint(a).z_bottom - firstPoint(b).z_bottom);
      for (let i = 1; i < stack.length; i++)
        if (
          Math.fround(firstPoint(stack[i - 1]!).z_top) !==
            Math.fround(firstPoint(stack[i]!).z_bottom) ||
          !sameFootprint(stack[0]!, stack[i]!)
        )
          throw new Error("Joined sight caps must form one contiguous stack");
      assembled.push({
        ...shape,
        points: shape.points.map((p) => ({
          ...p,
          z_bottom: firstPoint(stack[0]!).z_bottom,
          z_top: firstPoint(stack.at(-1)!).z_top,
        })),
      });
      continue;
    }
    const canonical: SightObstacle["points"] = [];
    const polygons = group.map((index) => [
      sight[index]!.points.map((p) => {
        let vertex = canonical.find((q) => Math.hypot(p.x - q.x, p.y - q.y) < 1e-5);
        if (!vertex) {
          vertex = p;
          canonical.push(p);
        }
        return [vertex.x, vertex.y] as [number, number];
      }),
    ]);
    for (let i = 0; i < polygons.length; i++)
      for (let j = 0; j < i; j++)
        if (polygonClipping.intersection(polygons[i]!, polygons[j]!).length)
          throw new Error("Joined sight volumes overlap instead of meeting along a seam");
    const union = polygonClipping.union(polygons[0]!, ...polygons.slice(1));
    if (union.length !== 1 || union[0]!.length !== 1)
      throw new Error("Joined sight volumes must form one contour without holes");
    const originals = canonical;
    const first = firstPoint(shape);
    const points = union[0]![0]!.slice(0, -1).map(([x, y]) => {
      const original = originals.find((p) => Math.hypot(p.x - x, p.y - y) < 1e-5);
      if (!original)
        throw new Error("Sight union introduced a vertex outside the authored contours");
      return { ...original, z_bottom: first.z_bottom, z_top: first.z_top };
    });
    const contour = points.filter((p, i) => {
      const a = points[(i + points.length - 1) % points.length]!,
        b = points[(i + 1) % points.length]!;
      return (
        Math.abs((p.x - a.x) * (b.y - a.y) - (p.y - a.y) * (b.x - a.x)) >
        1e-8 * Math.hypot(b.x - a.x, b.y - a.y)
      );
    });
    if (contour.length < 3) throw new Error("Sight assembly produced a degenerate contour");
    assembled.push({ ...shape, points: contour });
  }
  const remap = (index: number) => {
    const next = indices.get(index);
    if (next === undefined) throw new Error("Invalid sight reference during assembly");
    return next;
  };
  geometry.sight_obstacles = assembled;
  for (const mask of geometry.masks ?? []) mask.obstacle_indices = mask.obstacle_indices.map(remap);
  for (const transition of geometry.movement_transitions ?? []) {
    if (transition.initial_sight) transition.initial_sight = transition.initial_sight.map(remap);
    if (transition.applied_sight) transition.applied_sight = transition.applied_sight.map(remap);
  }
}
