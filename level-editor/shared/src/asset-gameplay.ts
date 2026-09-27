import type { LightSector, MaterialSector, Point, SightObstacle, SoundSource } from "./level.ts";
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
  /** Asset-local navigation partition; distinct partitions never merge across a gate. */
  navigationRegion?: string;
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
  /** Local 3D sockets joining another lift segment after placement. Every socket must match. */
  joins?: [number, number, number][];
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
export interface AssetMaterialRegion {
  id: string;
  node: string;
  /** Local 3D vertices, projected after placement. */
  polygon: [number, number, number][];
  /** Material codes 0–8; 9 selects the map default. */
  material: number;
  /** Register in the ground-layer lookup, independently of obstacle links. */
  ground: boolean;
  /** Owning asset's part nodes whose impact material lookup uses this region. */
  obstacles: string[];
}
export interface AssetGameplay {
  version: 1;
  /** Reuse part obstacles or disable them; explicit gameplay volumes remain independent. */
  collision: "parts" | "none";
  /** Gameplay volumes attached to an existing frame; no rendered mesh is required. */
  volumes?: {
    id: string;
    node: string;
    shape: Omit<SightObstacle, "projection_area" | "material_indices">;
  }[];
  /** Omit to derive movement from sight solids; an explicit list replaces that derivation. */
  movementBlockers?: AssetWalkableSurface[];
  /** Plane-local openings in this asset's derived movement collision, never in other assets. */
  movementClearances?: AssetWalkableSurface[];
  surfaces: AssetWalkableSurface[];
  doors: AssetDoor[];
  lifts?: AssetLift[];
  interiors?: AssetInterior[];
  materials?: AssetMaterialRegion[];
  /** Map-wide defaults supplied by a terrain asset. Ambience is mission-owned. */
  environment?: { forest: boolean; defaultMaterial: number };
  sounds?: AssetSoundSource[];
  lights?: AssetLightRegion[];
  jumpZones?: AssetJumpZone[];
  jumpPairs?: AssetJumpPair[];
  jumpSegments?: AssetJumpSegment[];
  /** Nonvisual movement changes. Visual/sight/mask transitions require separate authoring. */
  movementTransitions?: AssetMovementTransition[];
}
export interface AssetLightRegion {
  id: string;
  node: string;
  /** Planar local 3D contour; the receiving surface determines its compiled layer. */
  polygon: [number, number, number][];
  /** Mission ambience bit mask controlling this region, not a mission selection. */
  ambiences: number;
}
export interface AssetJumpZone {
  id: string;
  node: string;
  polygon: [number, number, number][];
  /** An unblocked point on the receiving movement surface. */
  anchor: [number, number, number];
  helperNeeded: boolean;
}
export interface AssetJumpSegment {
  id: string;
  node: string;
  long: boolean;
  /** Shared local 3D socket; must match one complementary edge after placement. */
  join: [number, number, number];
  edge: AssetJumpPair["edges"][number];
}
export interface AssetJumpPair {
  id: string;
  node: string;
  long: boolean;
  /** Each edge names its home zone; destination links are rebuilt during compilation. */
  edges: [
    { zone: string; a: [number, number, number]; b: [number, number, number] },
    { zone: string; a: [number, number, number]; b: [number, number, number] },
  ];
}
export interface AssetMovementTransition {
  id: string;
  node: string;
  waypoint: [number, number, number];
  active: boolean;
  definitive: boolean;
  initial: AssetWalkableSurface[];
  applied: AssetWalkableSurface[];
  /** Trigger contours at the waypoint's local elevation; empty means externally activated. */
  applyPolygon: Point[];
  noApplyPolygon: Point[];
}
export interface AssetSoundSource {
  id: string;
  node: string;
  /** Shared sound-bank sample identity, not a level source index. */
  sample: number;
  kind: 0 | 1 | 2 | 3;
  active: boolean;
  delay?: [number, number, number];
  /** Acoustic altitude category, independent of geometric elevation. */
  altitude: 0 | 1 | 2 | 3;
  ambiences: number;
  /** Omitted for a global emitter. Distances use game units, volumes use percent. */
  spatial?: {
    polyline: [number, number, number][];
    innerDistance: number;
    outerDistance: number;
    innerVolume: number;
    outerVolume: number;
    noiseCoveringDistance: number;
  };
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
  material_sectors?: MaterialSector[];
  sight_material_indices?: number[];
  map_settings?: { forest_level: boolean; default_material: number };
  sound_sources?: SoundSource[];
  light_sectors?: LightSector[];
  jump_zones?: {
    polygon: { points: Point[] };
    sector: number;
    layer: number;
    helper_needed: boolean;
  }[];
  jump_line_pairs?: {
    line1: {
      point_a: [number, number, number];
      point_b: [number, number, number];
      jump_zone_index: number;
    };
    line2: {
      point_a: [number, number, number];
      point_b: [number, number, number];
      jump_zone_index: number;
    };
    jump_long: boolean;
  }[];
  movement_transitions?: {
    id: string;
    waypoint: Point;
    sector: number;
    layer: number;
    active: boolean;
    definitive: boolean;
    apply_polygon: { points: Point[] };
    no_apply_polygon: { points: Point[] };
    motion_changes: { layer: number; sector: number; changing_obstacle: number }[];
  }[];
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
  if (
    data.environment !== undefined &&
    (descriptor.editor_usage !== "map-background" ||
      !data.environment ||
      typeof data.environment.forest !== "boolean" ||
      !Number.isInteger(data.environment.defaultMaterial) ||
      data.environment.defaultMaterial < 0 ||
      data.environment.defaultMaterial > 8)
  )
    fail("invalid terrain environment defaults");
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
  if (data.movementTransitions !== undefined && !Array.isArray(data.movementTransitions))
    fail("invalid movement transitions");
  for (const transition of data.movementTransitions ?? []) {
    feature(transition);
    if (
      !point(transition.waypoint, 3) ||
      typeof transition.active !== "boolean" ||
      typeof transition.definitive !== "boolean" ||
      !Array.isArray(transition.initial) ||
      !Array.isArray(transition.applied) ||
      (!transition.initial.length && !transition.applied.length)
    )
      fail(`invalid movement transition ${transition.id}`);
    for (const contour of [transition.applyPolygon, transition.noApplyPolygon])
      if (!(Array.isArray(contour) && contour.length === 0)) polygon(contour);
  }
  const integer = (n: unknown, max: number): n is number =>
    typeof n === "number" && Number.isInteger(n) && n >= 0 && n <= max;
  if (data.jumpZones !== undefined && !Array.isArray(data.jumpZones)) fail("invalid jump zones");
  if (data.jumpPairs !== undefined && !Array.isArray(data.jumpPairs)) fail("invalid jump pairs");
  const jumpZones = new Set<string>();
  for (const zone of data.jumpZones ?? []) {
    feature(zone);
    if (
      !point(zone.anchor, 3) ||
      typeof zone.helperNeeded !== "boolean" ||
      !Array.isArray(zone.polygon) ||
      zone.polygon.length < 3 ||
      !zone.polygon.every((p) => point(p, 3))
    )
      fail(`invalid jump zone ${zone.id}`);
    jumpZones.add(zone.id);
  }
  const usedJumpZones = new Set<string>();
  if (data.jumpSegments !== undefined && !Array.isArray(data.jumpSegments))
    fail("invalid jump segments");
  for (const segment of data.jumpSegments ?? []) {
    feature(segment);
    const edge = segment.edge;
    if (
      typeof segment.long !== "boolean" ||
      !point(segment.join, 3) ||
      !edge ||
      !jumpZones.has(edge.zone) ||
      !point(edge.a, 3) ||
      !point(edge.b, 3)
    )
      fail(`invalid jump segment or missing zone ${segment.id}`);
    usedJumpZones.add(edge.zone);
  }
  for (const pair of data.jumpPairs ?? []) {
    feature(pair);
    if (typeof pair.long !== "boolean" || !Array.isArray(pair.edges) || pair.edges.length !== 2)
      fail(`invalid jump pair ${pair.id}`);
    for (const edge of pair.edges) {
      if (!edge || !jumpZones.has(edge.zone) || !point(edge.a, 3) || !point(edge.b, 3))
        fail(`invalid jump edge or missing zone ${pair.id}`);
      usedJumpZones.add(edge.zone);
    }
  }
  if ([...jumpZones].some((id) => !usedJumpZones.has(id))) fail("jump zone has no paired edge");
  if (data.lights !== undefined && !Array.isArray(data.lights)) fail("invalid light regions");
  for (const light of data.lights ?? []) {
    feature(light);
    if (
      !integer(light.ambiences, 4294967295) ||
      !Array.isArray(light.polygon) ||
      light.polygon.length < 3 ||
      !light.polygon.every((p) => point(p, 3))
    )
      fail(`invalid light region ${light.id}`);
  }
  if (data.sounds !== undefined && !Array.isArray(data.sounds)) fail("invalid sound sources");
  for (const sound of data.sounds ?? []) {
    feature(sound);
    if (
      !integer(sound.sample, 2147483647) ||
      !integer(sound.kind, 3) ||
      !integer(sound.altitude, 3) ||
      !integer(sound.ambiences, 4294967295) ||
      typeof sound.active !== "boolean"
    )
      fail(`invalid sound source ${sound.id}`);
    if (
      sound.kind === 2
        ? !Array.isArray(sound.delay) ||
          sound.delay.length !== 3 ||
          !sound.delay.every((n) => integer(n, 65535)) ||
          sound.delay[0] > sound.delay[1] ||
          sound.delay[2] === 65535
        : sound.delay !== undefined
    )
      fail(`invalid sound delay ${sound.id}`);
    const s = sound.spatial;
    if (
      s !== undefined &&
      (!s ||
        !Array.isArray(s.polyline) ||
        !s.polyline.length ||
        !s.polyline.every((p) => point(p, 3)) ||
        !integer(s.innerDistance, 65535) ||
        !integer(s.outerDistance, 65535) ||
        s.innerDistance > s.outerDistance ||
        !integer(s.innerVolume, 100) ||
        !integer(s.outerVolume, 100) ||
        !integer(s.noiseCoveringDistance, 65535))
    )
      fail(`invalid sound geometry ${sound.id}`);
  }
  if (data.volumes !== undefined && !Array.isArray(data.volumes)) fail("invalid gameplay volumes");
  const volumes = new Set<string>();
  for (const volume of data.volumes ?? []) {
    feature(volume);
    if (nodes.has(volume.id)) fail("gameplay volume IDs must not shadow part nodes");
    volumes.add(volume.id);
    const shape = volume.shape;
    if (
      !shape ||
      !Array.isArray(shape.points) ||
      shape.points.length < 3 ||
      !shape.points.every(
        (p) => p && [p.x, p.y, p.z_bottom, p.z_top].every(Number.isFinite) && p.z_bottom <= p.z_top,
      ) ||
      ![shape.solid, shape.opaque, shape.mouse, shape.show_shadow_polygon].every(
        (v) => typeof v === "boolean",
      ) ||
      !Number.isInteger(shape.default_material) ||
      shape.default_material < 0 ||
      shape.default_material > 9 ||
      "projection_area" in shape ||
      "material_indices" in shape
    )
      fail(`invalid gameplay volume ${volume.id}`);
  }
  if (data.materials !== undefined && !Array.isArray(data.materials)) fail("invalid materials");
  for (const region of data.materials ?? []) {
    feature(region);
    if (
      !Array.isArray(region.polygon) ||
      region.polygon.length < 3 ||
      !region.polygon.every((p) => point(p, 3)) ||
      !Number.isInteger(region.material) ||
      region.material < 0 ||
      region.material > 9 ||
      typeof region.ground !== "boolean" ||
      !Array.isArray(region.obstacles) ||
      region.obstacles.some((node) => !nodes.has(node) && !volumes.has(node)) ||
      new Set(region.obstacles).size !== region.obstacles.length ||
      (!region.ground && !region.obstacles.length)
    )
      fail(`invalid material region ${region.id}`);
    if (region.obstacles.some((node) => nodes.has(node)) && data.collision !== "parts")
      fail(`material region ${region.id} references disabled obstacles`);
  }
  if (data.movementBlockers !== undefined && !Array.isArray(data.movementBlockers))
    fail("invalid movement blockers");
  if (data.movementClearances !== undefined && !Array.isArray(data.movementClearances))
    fail("invalid movement clearances");
  for (const surface of [
    ...data.surfaces,
    ...(data.movementBlockers ?? []),
    ...(data.movementClearances ?? []),
    ...(data.movementTransitions ?? []).flatMap((t) => [...t.initial, ...t.applied]),
  ]) {
    feature(surface);
    polygon(surface.polygon);
    if (
      surface.navigationRegion !== undefined &&
      (typeof surface.navigationRegion !== "string" ||
        !surface.navigationRegion.trim() ||
        !data.surfaces.includes(surface) ||
        data.lifts?.some((lift) => lift.surface === surface.id))
    )
      fail("navigation regions require nonempty labels on ordinary walkable surfaces");
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
      lift.joins !== undefined &&
      (!Array.isArray(lift.joins) || !lift.joins.length || !lift.joins.every((p) => point(p, 3)))
    )
      fail(`invalid lift joins: ${lift.id}`);
    if (
      !Array.isArray(lift.doors) ||
      (!lift.joins && (lift.doors.length < 2 || !lift.doors.some((d) => d.type === 5)))
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
