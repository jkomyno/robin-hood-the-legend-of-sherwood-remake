import type { Point, SightObstacle } from "./level.ts";
import type { ProjectionAssetDescriptor } from "./projection-assets.ts";

/** All coordinates belong to the named mesh part's local game frame. No level indices. */
export interface AssetWalkableSurface {
  id: string;
  node: string;
  polygon: Point[];
  /** Constant height or one height per polygon vertex; the surface must be planar. */
  height: number | number[];
  /** Holes lie on the same plane, in the same local XY frame. */
  holes?: Point[][];
}
export interface AssetDoor {
  id: string;
  node: string;
  polygon: Point[];
  /** Local [x, y, elevation]; endpoints resolve against assembled walkable surfaces. */
  outside: [number, number, number];
  inside: [number, number, number];
  middle: [number, number, number];
  type: number;
  locked: boolean;
  unlockable: boolean;
  active?: boolean;
  lockedVillains?: boolean;
  lockedCivilians?: boolean;
  /** Alternate lock rules; activation still requires an authored state transition. */
  afterTransition?: {
    locked: boolean;
    unlockable: boolean;
    lockedVillains: boolean;
    lockedCivilians: boolean;
  };
}
export interface AssetLift {
  id: string;
  node: string;
  /** Asset-local surface ID; no runtime sector or layer number. */
  surface: string;
  type: 1 | 2 | 3;
  /** Local ground-plane direction; transformed with the owning part. */
  direction: Point;
  doors: AssetDoor[];
}
export interface AssetInterior {
  id: string;
  node: string;
  /** Entrances share one virtual interior; occupants are authored separately. */
  doors: AssetDoor[];
}
export interface AssetGameplay {
  version: 1;
  /** Reuse asset-local part obstacles, or explicitly declare a visual-only asset. */
  collision: "parts" | "none";
  /** Omit to derive movement from sight solids; an explicit list replaces that derivation. */
  movementBlockers?: AssetWalkableSurface[];
  surfaces: AssetWalkableSurface[];
  doors: AssetDoor[];
  lifts?: AssetLift[];
  interiors?: AssetInterior[];
}
export type GameplayAssetDescriptor = ProjectionAssetDescriptor & { gameplay?: AssetGameplay };

/** A generated interchange schema; indices are assigned afresh on each compilation. */
export interface CompiledAssetGeometry {
  /** Authoring diagnostics, also surfaced in the export summary. */
  warnings?: string[];
  motion_data: {
    layers: {
      is_lift: boolean;
      state_id: number;
      polygon: { points: Point[] };
      skeleton_segments: never[];
      flags: number;
      obstacles: { state_id: number; polygon: { points: Point[] } }[];
    }[][];
    graph_bytes: never[];
  };
  sight_obstacles: SightObstacle[];
  doors: {
    door_type: number;
    active: boolean;
    locked_pc: boolean;
    unlockable: boolean;
    locked_npc_villain: boolean;
    locked_npc_civilian: boolean;
    locked_pc_after_patch: boolean;
    unlockable_after_patch: boolean;
    locked_npc_villain_after_patch: boolean;
    locked_npc_civilian_after_patch: boolean;
    door_sector: { points: Point[] };
    point_out: Point;
    sector_out: number;
    layer_out: number;
    point_mid: Point;
    point_in: Point;
    sector_in: number;
    layer_in: number;
  }[];
  buildings?: { Building: { doors: CompiledAssetGeometry["doors"] } }[];
  lifts?: {
    motion_area_index: number;
    lift_type: number;
    direction: number;
    doors: CompiledAssetGeometry["doors"];
  }[];
}

export function validateAssetGameplay(
  value: unknown,
  descriptor: ProjectionAssetDescriptor,
): asserts value is AssetGameplay {
  const fail = (message: string): never => {
    throw new Error(`Asset ${descriptor.id}: ${message}`);
  };
  if (!value || typeof value !== "object") fail("missing gameplay definition");
  const data = value as AssetGameplay;
  if (data.version !== 1 || !["parts", "none"].includes(data.collision))
    fail("invalid gameplay version or collision mode");
  const point = (p: unknown, length: number) =>
    Array.isArray(p) &&
    p.length === length &&
    p.every((v) => typeof v === "number" && Number.isFinite(v));
  const nodes = new Set(descriptor.parts.map((part) => part.node));
  const ids = new Set<string>();
  const feature = (f: { id: string; node: string }) => {
    if (!f || typeof f.id !== "string" || !f.id || ids.has(f.id))
      fail("gameplay IDs must be nonempty and unique");
    ids.add(f.id);
    if (!nodes.has(f.node) && !(descriptor.editor_usage === "map-background" && f.node === "$root"))
      fail(`unknown gameplay node ${f.node}`);
  };
  const polygon = (points: unknown) => {
    if (!Array.isArray(points) || points.length < 3 || !points.every((p) => point(p, 2)))
      fail("invalid gameplay polygon");
  };
  if (![data.surfaces, data.doors].every(Array.isArray))
    fail("surfaces and doors must be explicitly declared");
  const legacySpawns = (value as { spawns?: unknown }).spawns;
  if (legacySpawns !== undefined && (!Array.isArray(legacySpawns) || legacySpawns.length))
    fail("Player spawns belong to missions, not map assets");
  if (data.movementBlockers !== undefined && !Array.isArray(data.movementBlockers))
    fail("invalid movement blockers");
  for (const surface of [...data.surfaces, ...(data.movementBlockers ?? [])]) {
    feature(surface);
    polygon(surface.polygon);
    if (
      !(typeof surface.height === "number" && Number.isFinite(surface.height)) &&
      !(
        Array.isArray(surface.height) &&
        surface.height.length === surface.polygon.length &&
        surface.height.every((z) => typeof z === "number" && Number.isFinite(z))
      )
    )
      fail("invalid surface height");
    if (surface.holes !== undefined) {
      if (!Array.isArray(surface.holes)) fail("invalid surface holes");
      for (const hole of surface.holes) polygon(hole);
    }
  }
  const validateDoor = (door: AssetDoor, kind: "ordinary" | "lift" | "interior") => {
    const lift = kind === "lift";
    feature(door);
    // A connection can have no clickable sector while still linking navigation areas.
    if (!(Array.isArray(door.polygon) && door.polygon.length === 0)) polygon(door.polygon);
    if (
      !point(door.outside, 3) ||
      !point(door.inside, 3) ||
      !point(door.middle, 3) ||
      !(lift ? [4, 5, 6] : kind === "interior" ? [1, 2] : [0, 3, 7]).includes(door.type) ||
      typeof door.locked !== "boolean" ||
      typeof door.unlockable !== "boolean"
    )
      fail(`invalid door ${door.id}`);
    for (const key of ["active", "lockedVillains", "lockedCivilians"] as const)
      if (door[key] !== undefined && typeof door[key] !== "boolean")
        fail(`invalid door ${door.id} ${key}`);
    if (door.afterTransition !== undefined) {
      if (!door.afterTransition || typeof door.afterTransition !== "object")
        fail(`invalid door ${door.id} transition locks`);
      for (const key of ["locked", "unlockable", "lockedVillains", "lockedCivilians"] as const)
        if (typeof door.afterTransition[key] !== "boolean")
          fail(`invalid door ${door.id} transition ${key}`);
    }
  };
  for (const door of data.doors) validateDoor(door, "ordinary");
  if (data.lifts !== undefined && !Array.isArray(data.lifts)) fail("invalid lifts");
  const liftSurfaces = new Set<string>();
  for (const lift of data.lifts ?? []) {
    feature(lift);
    const surface = data.surfaces.find((s) => s.id === lift.surface);
    if (!surface || surface.node !== lift.node || liftSurfaces.has(lift.surface))
      fail(`lift ${lift.id} needs its own surface on the same node`);
    liftSurfaces.add(lift.surface);
    if (
      ![1, 2, 3].includes(lift.type) ||
      !point(lift.direction, 2) ||
      Math.hypot(...lift.direction) < 1e-6
    )
      fail(`invalid lift type or direction: ${lift.id}`);
    if (
      !Array.isArray(lift.doors) ||
      lift.doors.length < 2 ||
      !lift.doors.some((d) => d.type === 5)
    )
      fail(`lift ${lift.id} needs at least two traversal doors including a low door`);
    for (const door of lift.doors) {
      if (door.node !== lift.node) fail(`lift ${lift.id} door must use its owning node`);
      validateDoor(door, "lift");
    }
  }
  if (data.interiors !== undefined && !Array.isArray(data.interiors)) fail("invalid interiors");
  for (const interior of data.interiors ?? []) {
    feature(interior);
    if (!Array.isArray(interior.doors) || !interior.doors.length)
      fail(`interior ${interior.id} has no entrance`);
    for (const door of interior.doors) {
      if (door.node !== interior.node)
        fail(`interior ${interior.id} door must use its owning node`);
      validateDoor(door, "interior");
    }
  }
}
