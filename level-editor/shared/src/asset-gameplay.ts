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
}
export interface AssetSpawn {
  id: string;
  node: string;
  position: [number, number, number];
}
export interface AssetGameplay {
  version: 1;
  /** Reuse asset-local part obstacles, or explicitly declare a visual-only asset. */
  collision: "parts" | "none";
  surfaces: AssetWalkableSurface[];
  doors: AssetDoor[];
  spawns: AssetSpawn[];
}
export type GameplayAssetDescriptor = ProjectionAssetDescriptor & { gameplay?: AssetGameplay };

/** A generated interchange schema; indices are assigned afresh on each compilation. */
export interface CompiledAssetGeometry {
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
  spawn: { position: Point; sector: number; layer: number; projection_area: number | null };
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
  if (![data.surfaces, data.doors, data.spawns].every(Array.isArray))
    fail("surfaces, doors and spawns must be explicitly declared");
  for (const surface of data.surfaces) {
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
  for (const door of data.doors) {
    feature(door);
    polygon(door.polygon);
    if (
      !point(door.outside, 3) ||
      !point(door.inside, 3) ||
      !point(door.middle, 3) ||
      ![0, 3].includes(door.type) ||
      typeof door.locked !== "boolean" ||
      typeof door.unlockable !== "boolean"
    )
      fail(`invalid door ${door.id}`);
  }
  for (const spawn of data.spawns) {
    feature(spawn);
    if (!point(spawn.position, 3)) fail(`invalid spawn ${spawn.id}`);
  }
}
