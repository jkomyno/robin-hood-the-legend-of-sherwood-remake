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
  /** Asset-local navigation region, optionally spanning height planes; distinct regions never merge. */
  navigationRegion?: string;
  /** Receiving-surface material and ordered asset-local material-region references. */
  projectionMaterials?: {
    defaultMaterial: number;
    regions: string[];
    /** Local bounding height for overlap priority; equal heights use surface order within the asset. */
    priorityHeight?: number;
    /** Higher values win equal-height overlaps across independent placements. */
    priority?: number;
    /** Local receiving footprint, including blocked portions omitted from walking contours. */
    footprint?: [number, number, number][];
  };
}
export interface AssetDoor {
  id: string;
  node: string;
  polygon: Point[];
  /** Local [x, y, elevation]; endpoints resolve against assembled walkable surfaces. */
  outside: [number, number, number];
  inside: [number, number, number];
  middle: [number, number, number];
  /** Optional unblocked local points selecting receiving areas independently of door coordinates. */
  outsideAnchor?: [number, number, number];
  insideAnchor?: [number, number, number];
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
  /** Optional passage sockets; coincident opposing sockets connect rooms after placement. */
  joins?: { point: [number, number, number]; direction: Point }[];
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
  /** Authored contours replace implicit movement derivation; movementSolids can select additional solids. */
  movementBlockers?: AssetWalkableSurface[];
  /** Explicit part/volume IDs supplying permanent movement solids, independently of sight states. */
  movementSolids?: string[];
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
  masks?: AssetOcclusionMask[];
  jumpZones?: AssetJumpZone[];
  jumpPairs?: AssetJumpPair[];
  jumpSegments?: AssetJumpSegment[];
  /** Independent navigation, sight, mask and door state links; visual resources are separate. */
  movementTransitions?: AssetMovementTransition[];
}
export interface AssetOcclusionMask {
  id: string;
  node: string;
  /** Explicit local 3D coverage, including cutouts between triangles. */
  triangles: import("./compile-mask-geometry.ts").MaskTriangle[];
  /** Local point on the receiving navigation surface; may lie inside a blocker. */
  anchor: [number, number, number];
  view: boolean;
  /** Local boundary; its projected front envelope controls character masking. */
  characterBoundary?: [number, number, number][];
  /** Defaults to true. False preserves an authored open polyline without a closing edge. */
  characterBoundaryClosed?: boolean;
  /** Local boundary; its world XY front envelope controls projectile masking. */
  projectileBoundary?: [number, number, number][];
  /** Defaults to true, independently of the character boundary. */
  projectileBoundaryClosed?: boolean;
  /** Local part/volume IDs used for the projectile/flying-human altitude test. */
  obstacles: string[];
}
export interface AssetLightRegion {
  id: string;
  node: string;
  /** Planar local 3D contour; defaults to receivers on the same plane. */
  polygon: [number, number, number][];
  /** Optional local anchors selecting receiving layers independently of the contour plane. */
  receivers?: [number, number, number][];
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
  /** Shared local 3D socket; the jump is available only when one complementary edge matches. */
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
  /** Local receiving-area anchor when the reference point lies outside its linked surface. */
  waypointAnchor?: [number, number, number];
  active: boolean;
  definitive: boolean;
  initial: AssetWalkableSurface[];
  applied: AssetWalkableSurface[];
  /** Local part/volume IDs enabled before and after the transition, respectively. */
  initialSight?: string[];
  appliedSight?: string[];
  initialMasks?: string[];
  appliedMasks?: string[];
  /** Local ordinary/interior door IDs. Lift traversal doors cannot bind map patches. */
  doorLinks?: { mode: "trigger-transition" | "swap-rights"; ids: string[] };
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
  /** Baked typed masks; obstacle references use this compilation's sight array. */
  masks?: import("./level.ts").Mask[];
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
    initial_sight?: number[];
    applied_sight?: number[];
    /** Indices into this compilation's mask array, not native per-layer indices. */
    initial_masks?: number[];
    applied_masks?: number[];
    door_links?: { mode: "trigger-transition" | "swap-rights"; indices: number[] };
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
  const changingSight = new Set<string>();
  if (data.masks !== undefined && !Array.isArray(data.masks)) fail("invalid masks");
  const maskIds = new Set<string>();
  for (const mask of data.masks ?? []) {
    feature(mask);
    if (
      !point(mask.anchor, 3) ||
      typeof mask.view !== "boolean" ||
      !Array.isArray(mask.triangles) ||
      !mask.triangles.length ||
      !mask.triangles.every(
        (triangle) =>
          Array.isArray(triangle) && triangle.length === 3 && triangle.every((p) => point(p, 3)),
      ) ||
      !Array.isArray(mask.obstacles) ||
      new Set(mask.obstacles).size !== mask.obstacles.length
    )
      fail(`invalid mask ${mask.id}`);
    for (const [boundary, closed] of [
      [mask.characterBoundary, mask.characterBoundaryClosed],
      [mask.projectileBoundary, mask.projectileBoundaryClosed],
    ] as const) {
      if (closed !== undefined && (typeof closed !== "boolean" || boundary === undefined))
        fail(`invalid mask boundary closure ${mask.id}`);
      if (
        boundary !== undefined &&
        (!Array.isArray(boundary) ||
          boundary.length < (closed === false ? 2 : 3) ||
          !boundary.every((p) => point(p, 3)))
      )
        fail(`invalid mask boundary ${mask.id}`);
    }
    for (const ref of mask.obstacles)
      if (
        typeof ref !== "string" ||
        !(
          data.volumes?.some((volume) => volume.id === ref) ||
          (data.collision === "parts" &&
            descriptor.parts.some((part) => part.node === ref && part.obstacle_local_game))
        )
      )
        fail(`mask ${mask.id} references missing obstacle ${ref}`);
    if (!mask.view && !mask.characterBoundary && !mask.projectileBoundary && !mask.obstacles.length)
      fail(`mask ${mask.id} has no application rule`);
    maskIds.add(mask.id);
  }
  const changingMasks = new Set<string>();
  const triggeringDoors = new Set<string>();
  for (const transition of data.movementTransitions ?? []) {
    feature(transition);
    if (
      !point(transition.waypoint, 3) ||
      (transition.waypointAnchor !== undefined && !point(transition.waypointAnchor, 3)) ||
      typeof transition.active !== "boolean" ||
      typeof transition.definitive !== "boolean" ||
      !Array.isArray(transition.initial) ||
      !Array.isArray(transition.applied) ||
      (!transition.initial.length &&
        !transition.applied.length &&
        !transition.initialSight?.length &&
        !transition.appliedSight?.length &&
        !transition.initialMasks?.length &&
        !transition.appliedMasks?.length &&
        !transition.doorLinks)
    )
      fail(`invalid movement transition ${transition.id}`);
    for (const refs of [transition.initialMasks, transition.appliedMasks]) {
      if (refs === undefined) continue;
      if (!Array.isArray(refs)) fail("invalid mask transition references");
      for (const ref of refs) {
        if (!maskIds.has(ref) || changingMasks.has(ref))
          fail(`invalid or multiply controlled mask ${ref}`);
        changingMasks.add(ref);
      }
    }
    const links = transition.doorLinks;
    if (links !== undefined) {
      if (
        !links ||
        !["trigger-transition", "swap-rights"].includes(links.mode) ||
        !Array.isArray(links.ids) ||
        !links.ids.length ||
        new Set(links.ids).size !== links.ids.length
      )
        fail("invalid transition door links");
      const doors = [...data.doors, ...(data.interiors ?? []).flatMap((room) => room.doors)];
      for (const id of links.ids) {
        if (typeof id !== "string" || !doors.some((door) => door.id === id))
          fail(`transition references missing ordinary/interior door ${id}`);
        if (links.mode === "trigger-transition") {
          if (triggeringDoors.has(id)) fail(`door ${id} triggers multiple transitions`);
          triggeringDoors.add(id);
        }
      }
    }
    for (const refs of [transition.initialSight, transition.appliedSight]) {
      if (refs === undefined) continue;
      if (!Array.isArray(refs)) fail("invalid sight transition references");
      for (const ref of refs) {
        if (
          typeof ref !== "string" ||
          changingSight.has(ref) ||
          !(
            data.volumes?.some((v) => v.id === ref) ||
            (data.collision === "parts" && nodes.has(ref))
          )
        )
          fail(`invalid or multiply controlled sight obstacle ${ref}`);
        changingSight.add(ref);
      }
    }
    for (const contour of [transition.applyPolygon, transition.noApplyPolygon])
      if (!(Array.isArray(contour) && contour.length === 0)) polygon(contour);
  }
  if (data.movementSolids !== undefined) {
    if (
      !Array.isArray(data.movementSolids) ||
      new Set(data.movementSolids).size !== data.movementSolids.length
    )
      fail("invalid permanent movement solids");
    for (const ref of data.movementSolids)
      if (
        typeof ref !== "string" ||
        !(
          data.volumes?.some((volume) => volume.id === ref && volume.shape.solid) ||
          (data.collision === "parts" &&
            descriptor.parts.some((part) => part.node === ref && part.obstacle_local_game?.solid))
        )
      )
        fail(`invalid permanent movement solid ${ref}`);
  }
  if (
    changingSight.size &&
    data.movementBlockers === undefined &&
    data.movementSolids === undefined
  )
    fail(
      "Sight transitions require explicit movement blockers or permanent movement solids; author navigation changes independently",
    );
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
    if (
      light.receivers !== undefined &&
      (!Array.isArray(light.receivers) ||
        !light.receivers.length ||
        !light.receivers.every((p) => point(p, 3)))
    )
      fail(`invalid light receivers ${light.id}`);
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
      (!region.ground &&
        !region.obstacles.length &&
        !data.surfaces.some(
          (surface) =>
            Array.isArray(surface.projectionMaterials?.regions) &&
            surface.projectionMaterials.regions.includes(region.id),
        ))
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
    if (surface.projectionMaterials !== undefined) {
      const projection = surface.projectionMaterials;
      if (
        !data.surfaces.includes(surface) ||
        !projection ||
        !Number.isInteger(projection.defaultMaterial) ||
        projection.defaultMaterial < 0 ||
        projection.defaultMaterial > 9 ||
        (projection.priorityHeight !== undefined && !Number.isFinite(projection.priorityHeight)) ||
        (projection.priority !== undefined && !Number.isFinite(projection.priority)) ||
        (projection.footprint !== undefined &&
          (!Array.isArray(projection.footprint) ||
            projection.footprint.length < 3 ||
            !projection.footprint.every((p) => point(p, 3)))) ||
        !Array.isArray(projection.regions) ||
        new Set(projection.regions).size !== projection.regions.length ||
        projection.regions.some((id) => !data.materials?.some((region) => region.id === id))
      )
        fail(`invalid projection materials on ${surface.id}`);
    }
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
    for (const key of ["outsideAnchor", "insideAnchor"] as const)
      if (door[key] !== undefined && !point(door[key], 3)) fail(`invalid door ${door.id} ${key}`);
    if (kind === "interior" && door.insideAnchor !== undefined)
      fail(`interior door ${door.id} cannot override its shared room with an inside anchor`);
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
    if (
      interior.joins !== undefined &&
      (!Array.isArray(interior.joins) ||
        !interior.joins.length ||
        interior.joins.some(
          (join) =>
            !join ||
            !point(join.point, 3) ||
            !point(join.direction, 2) ||
            Math.hypot(...join.direction) < 1e-6,
        ))
    )
      fail(`invalid interior joins: ${interior.id}`);
    if (!Array.isArray(interior.doors) || (!interior.doors.length && !interior.joins?.length))
      fail(`interior ${interior.id} has no entrance or passage socket`);
    for (const door of interior.doors) {
      if (door.node !== interior.node)
        fail(`interior ${interior.id} door must use its owning node`);
      validateDoor(door, "interior");
    }
  }
}
