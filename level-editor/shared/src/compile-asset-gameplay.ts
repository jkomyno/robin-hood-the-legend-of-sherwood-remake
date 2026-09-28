import polygonClipping, { type Polygon } from "polygon-clipping";
import { fixedPolygonBoolean } from "./fixed-polygon-boolean.ts";
import { assembleNavigationRegions, type NavigationPiece } from "./assemble-navigation-regions.ts";
import { assembleJumpSegments, type PlacedJumpSegment } from "./assemble-jump-segments.ts";
import { assembleLiftSegments, type PlacedLiftSegment } from "./assemble-lift-segments.ts";
import { assembleInteriors, type PlacedInterior } from "./assemble-interiors.ts";
import {
  partitionProjectionMaterials,
  type ProjectionMaterialSupport,
} from "./partition-projection-materials.ts";
import { partMatrix, transformedObstacle, type Level3D, type Level3DObject } from "./level3d.ts";
import { gameToScene, type Vec3 } from "./scene.ts";
import { sceneToGame } from "./geometry.ts";
import type { Point, SightObstacle } from "./level.ts";
import type { ProjectionAssetDescriptor } from "./projection-assets.ts";
import {
  validateAssetGameplay,
  type GameplayAssetDescriptor,
  type CompiledAssetGeometry,
  type AssetGameplay,
} from "./asset-gameplay.ts";

import { heightPlane, planeHeight, clipHeight, type HeightPlane } from "./gameplay-plane.ts";
import { quantizeGeneratedMotionPolygon, simplifyMotionRing } from "./motion-quantization.ts";
import { normalizeGeneratedMotion } from "./normalize-generated-motion.ts";
import { normalizeGameplayStateViews } from "./gameplay-state-views.ts";
import {
  maskBoundaryPolyline,
  rasterizeMaskGeometry,
  type MaskTriangle,
} from "./compile-mask-geometry.ts";
import {
  compileTransitionObstacles,
  type PlacedTransitionBlocker,
} from "./compile-movement-transitions.ts";

type Instance = {
  id: string;
  descriptor: GameplayAssetDescriptor;
  parts: Map<string, Level3DObject>;
  frames: Map<string, Level3DObject>;
  background: boolean;
};
const signedArea = (ring: Point[]) =>
  ring.reduce((sum, a, i) => {
    const b = ring[(i + 1) % ring.length]!;
    return sum + a[0] * b[1] - b[0] * a[1];
  }, 0) / 2;
function ring(points: Point[], label = "Gameplay polygon"): Point[] {
  // Plane construction in the runtime uses the first three vertices.
  // Remove straight-edge vertices introduced by polygon unions and clipping.
  const result = simplifyMotionRing(points);
  if (result.length < 3 || Math.abs(signedArea(result)) < 0.5)
    throw new Error(
      `${label} collapses after coordinate quantization (${JSON.stringify(points.slice(0, 8))})`,
    );
  // Consistent winding is required by movement edge authorization.
  if (signedArea(result) < 0) result.reverse();
  return result;
}
const polygon = (points: Point[]): Polygon => [[...points, points[0]!]];
function inside(p: Point, points: Point[]) {
  let hit = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const a = points[i]!,
      b = points[j]!;
    if (
      a[1] > p[1] !== b[1] > p[1] &&
      p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]
    )
      hit = !hit;
  }
  return hit;
}
function instances(
  document: Level3D,
  descriptors: ReadonlyMap<string, ProjectionAssetDescriptor>,
): Instance[] {
  const result = new Map<string, Instance>();
  const hidden = new Set(document.groups.filter((g) => g.hidden).map((g) => g.id));
  for (const part of document.objects) {
    if (part.hidden || (part.group && hidden.has(part.group))) continue;
    const match = /^asset:([^:]+):(.+)$/.exec(part.node);
    if (!match)
      throw new Error(
        `Object ${part.id} has no asset definition. Publish its gameplay in an asset before compiling.`,
      );
    const descriptor = descriptors.get(match[1]!);
    if (!descriptor) throw new Error(`Missing pinned asset ${match[1]}`);
    const id = `${part.group ?? part.id}/${match[1]}`;
    let instance = result.get(id);
    if (!instance) {
      instance = { id, descriptor, parts: new Map(), frames: new Map(), background: false };
      result.set(id, instance);
    }
    if (instance.parts.has(match[2]!))
      throw new Error(`Duplicate asset node ${part.node} in placement ${id}`);
    instance.parts.set(match[2]!, part);
  }
  // Explicit gameplay keeps its local frames even when a mesh part is hidden.
  // Entirely hidden placements still contribute no instance.
  for (const part of document.objects) {
    const match = /^asset:([^:]+):(.+)$/.exec(part.node);
    if (!match) continue;
    const instance = result.get(`${part.group ?? part.id}/${match[1]}`);
    if (!instance) continue;
    if (instance.frames.has(match[2]!))
      throw new Error(`Duplicate asset frame ${part.node} in placement ${instance.id}`);
    instance.frames.set(match[2]!, part);
  }
  for (const source of document.sceneAssets) {
    if (source.role !== "ground") continue;
    const descriptor = descriptors.get(source.id);
    if (!descriptor) throw new Error(`Ground asset ${source.id} has no pinned gameplay definition`);
    result.set(`ground/${source.id}`, {
      id: `ground/${source.id}`,
      descriptor,
      parts: new Map(),
      frames: new Map(),
      background: true,
    });
  }
  return [...result.values()].sort((a, b) => a.id.localeCompare(b.id, "en"));
}

/** Compile only placed editor assets. There is deliberately no datadir, source-map or level-record input. */
export function compileAssetGameplay(
  document: Level3D,
  descriptors: ReadonlyMap<string, ProjectionAssetDescriptor>,
  bounds: [number, number, number, number],
): CompiledAssetGeometry {
  ({ document, descriptors } = normalizeGameplayStateViews(document, descriptors));
  // Saved placements may contain old obstacle snapshots. Geometry authority is
  // the pinned asset; scene instances supply identity, visibility and transforms.
  document = {
    ...document,
    objects: document.objects.map((part) => {
      const match = /^asset:([^:]+):(.+)$/.exec(part.node);
      if (!match) return part;
      const definition = descriptors.get(match[1]!)?.parts.find((p) => p.node === match[2]);
      if (!definition) throw new Error(`Missing asset part definition ${part.node}`);
      return { ...part, obstacle: definition.obstacle_local_game };
    }),
  };
  const placements = instances(document, descriptors);
  const missing = [
    ...new Set(placements.filter((p) => !p.descriptor.gameplay).map((p) => p.descriptor.id)),
  ];
  if (missing.length)
    throw new Error(
      `Missing asset gameplay definitions (${missing.length}): ${missing.join(", ")}. Add local surfaces and door definitions to these assets; no source-level fallback is available.`,
    );
  if (
    document.splines?.length ||
    document.population?.actors.length ||
    document.population?.items.length
  )
    throw new Error(
      "Map compilation does not support spline gameplay or embedded mission population; keep NPCs and items in a separate mission",
    );
  if (document.groups.some((g) => g.states || g.patches) || document.objects.some((p) => p.patches))
    throw new Error(
      "Asset state transitions need gameplay compilation support before this map can be exported",
    );
  const project = (p: Vec3): Point => [quantize(p[0]), quantize(p[1] - p[2])];
  const warnings: string[] = [];
  const surfaces: {
    owner: string;
    polygon: Point[];
    holes: Point[][];
    plane: HeightPlane;
    lift?: string;
    navigationRegion?: string;
  }[] = [];
  const movementBlockers: typeof surfaces = [];
  const movementSolids: { owner: string; shape: SightObstacle }[] = [];
  const movementClearances: typeof surfaces = [];
  const transitionBlockers: PlacedTransitionBlocker[] = [];
  const projectionSupports: (ProjectionMaterialSupport & {
    plane: HeightPlane;
    navigationRegion?: string;
    lift?: string;
  })[] = [];
  const lights: {
    id: string;
    polygon: Point[];
    plane: HeightPlane;
    ambiences: number;
    receivers?: Vec3[];
  }[] = [];
  const placedMasks: {
    id: string;
    anchor: Vec3;
    triangles: MaskTriangle[];
    rules: Omit<import("./level.ts").Mask, "layer" | "box_top_left" | "box_size" | "mask_data">;
  }[] = [];
  const jumpZones: { id: string; polygon: Point[]; anchor: Vec3; helper: boolean }[] = [];
  const jumpSegments: PlacedJumpSegment[] = [];
  const jumpPairs: { id: string; long: boolean; edges: { zone: string; a: Vec3; b: Vec3 }[] }[] =
    [];
  const transitions: {
    id: string;
    waypoint: Vec3;
    waypointAnchor: Vec3;
    active: boolean;
    definitive: boolean;
    applyPolygon: Point[];
    noApplyPolygon: Point[];
    changes: { layer: number; sector: number; changing_obstacle: number }[];
    initialSight: number[];
    appliedSight: number[];
    initialMasks: string[];
    appliedMasks: string[];
    doorLinks?: { mode: "trigger-transition" | "swap-rights"; ids: string[] };
  }[] = [];
  let lifts: PlacedLiftSegment[] = [];
  const placedInteriors: PlacedInterior[] = [];
  const doors: {
    name: string;
    lift?: string;
    interior?: string;
    definition: AssetGameplay["doors"][number];
    outside: Vec3;
    inside: Vec3;
    outsideAnchor: Vec3;
    insideAnchor: Vec3;
    middle: Point;
    polygon: Point[];
  }[] = [];
  const sight: SightObstacle[] = [];
  const materials: NonNullable<CompiledAssetGeometry["material_sectors"]> = [];
  const groundMaterials: number[] = [];
  const sounds: NonNullable<CompiledAssetGeometry["sound_sources"]> = [];
  let mapSettings: CompiledAssetGeometry["map_settings"];
  const quantize = (n: number) => {
    const result = Math.round(n);
    if (!Number.isFinite(n) || result < -32768 || result > 32767)
      throw new Error("Asset gameplay exceeds signed 16-bit coordinates");
    return result;
  };
  for (const placement of placements) {
    const gameplay = placement.descriptor.gameplay!;
    validateAssetGameplay(gameplay, placement.descriptor);
    if (gameplay.environment) {
      const settings = {
        forest_level: gameplay.environment.forest,
        default_material: gameplay.environment.defaultMaterial,
      };
      if (
        mapSettings &&
        (mapSettings.forest_level !== settings.forest_level ||
          mapSettings.default_material !== settings.default_material)
      )
        throw new Error("Terrain assets disagree on map environment defaults");
      mapSettings = settings;
    }
    const transform = (node: string, point: Vec3): Vec3 => {
      let p = point;
      if (!placement.background || node !== "$root") {
        const part = placement.frames.get(node);
        if (!part) throw new Error(`${placement.id}: gameplay node ${node} is hidden or missing`);
        const matrix = partMatrix(document.camera, document, part);
        const local = gameToScene(document.camera, ...point);
        const world = [0, 1, 2].map(
          (row) =>
            matrix[row]! * local[0] +
            matrix[4 + row]! * local[1] +
            matrix[8 + row]! * local[2] +
            matrix[12 + row]!,
        ) as Vec3;
        p = sceneToGame(document.camera, world);
      }
      return [p[0] - bounds[0], p[1] - bounds[1], p[2]];
    };
    for (const zone of gameplay.jumpZones ?? [])
      jumpZones.push({
        id: `${placement.id}/${zone.id}`,
        anchor: transform(zone.node, zone.anchor),
        polygon: ring(
          zone.polygon.map((p) => project(transform(zone.node, p))),
          `${placement.id}/${zone.id}`,
        ),
        helper: zone.helperNeeded,
      });
    for (const pair of gameplay.jumpPairs ?? [])
      jumpPairs.push({
        id: `${placement.id}/${pair.id}`,
        long: pair.long,
        edges: pair.edges.map((edge) => ({
          zone: `${placement.id}/${edge.zone}`,
          a: transform(pair.node, edge.a),
          b: transform(pair.node, edge.b),
        })),
      });
    for (const segment of gameplay.jumpSegments ?? [])
      jumpSegments.push({
        id: `${placement.id}/${segment.id}`,
        long: segment.long,
        join: transform(segment.node, segment.join),
        edge: {
          zone: `${placement.id}/${segment.edge.zone}`,
          a: transform(segment.node, segment.edge.a),
          b: transform(segment.node, segment.edge.b),
        },
      });
    for (const light of gameplay.lights ?? []) {
      const points = light.polygon.map((p) => transform(light.node, p));
      lights.push({
        id: `${placement.id}/${light.id}`,
        polygon: ring(points.map(project), `${placement.id}/${light.id}`),
        plane: heightPlane(points.map(([x, y, z]): Vec3 => [x, y - z, z])),
        ambiences: light.ambiences,
        ...(light.receivers
          ? { receivers: light.receivers.map((p) => transform(light.node, p)) }
          : {}),
      });
    }
    for (const sound of gameplay.sounds ?? []) {
      const s = sound.spatial;
      // Global emitters still require their owning part to be present.
      if (!s) transform(sound.node, [0, 0, 0]);
      sounds.push({
        id: sound.sample,
        active: sound.active,
        source_kind: sound.kind,
        delayed_params: sound.delay ? [...sound.delay] : null,
        global: !s,
        polyline: s ? s.polyline.map((p) => project(transform(sound.node, p))) : null,
        inner_distance: s?.innerDistance ?? null,
        outer_distance: s?.outerDistance ?? null,
        inner_volume: s?.innerVolume ?? null,
        outer_volume: s?.outerVolume ?? null,
        noise_covering_distance: s?.noiseCoveringDistance ?? null,
        altitude: sound.altitude,
        ambience_filter: sound.ambiences,
      });
    }
    const partSight = new Map<string, SightObstacle>();
    const movementSolid = (id: string) =>
      gameplay.movementSolids?.includes(id) ?? gameplay.movementBlockers === undefined;
    const explicitSight = new Set([
      ...(gameplay.movementTransitions ?? []).flatMap((t) => [
        ...(t.initialSight ?? []),
        ...(t.appliedSight ?? []),
      ]),
      ...(gameplay.masks ?? []).flatMap((mask) => mask.obstacles),
    ]);
    if (gameplay.collision === "parts")
      for (const [node, part] of placement.frames) {
        if (!placement.parts.has(node) && !explicitSight.has(node)) continue;
        if (!part.obstacle) continue;
        const shape = transformedObstacle(document, part);
        // Keep per-vertex heights and flags, but rebuild all map-wide references.
        sight.push({
          ...shape,
          points: shape.points.map((p) => ({ ...p, x: p.x - bounds[0], y: p.y - bounds[1] })),
          projection_area: null,
          material_indices: [],
        });
        partSight.set(node, sight.at(-1)!);
        if (movementSolid(node)) movementSolids.push({ owner: placement.id, shape: sight.at(-1)! });
      }
    for (const volume of gameplay.volumes ?? []) {
      const shape: SightObstacle = {
        ...volume.shape,
        projection_area: null,
        material_indices: [],
        points: volume.shape.points.map((p) => {
          const bottom = transform(volume.node, [p.x, p.y, p.z_bottom]);
          const top = transform(volume.node, [p.x, p.y, p.z_top]);
          if (Math.hypot(bottom[0] - top[0], bottom[1] - top[1]) > 1e-5)
            throw new Error(`Gameplay volume ${volume.id} must remain vertical after placement`);
          return { x: top[0], y: top[1], z_bottom: bottom[2], z_top: top[2] };
        }),
      };
      sight.push(shape);
      partSight.set(volume.id, shape);
      if (movementSolid(volume.id)) movementSolids.push({ owner: placement.id, shape });
    }
    for (const id of gameplay.movementSolids ?? [])
      if (!partSight.has(id))
        throw new Error(`Permanent movement solid ${placement.id}/${id} is hidden or missing`);
    for (const mask of gameplay.masks ?? []) {
      const boundary = (points: Vec3[] | undefined, projected: boolean, closed = true) =>
        points
          ? maskBoundaryPolyline(
              points.map((point): Point => {
                const p = transform(mask.node, point);
                return projected ? project(p) : [quantize(p[0]), quantize(p[1])];
              }),
              closed,
            )
          : null;
      placedMasks.push({
        id: `${placement.id}/${mask.id}`,
        anchor: transform(mask.node, mask.anchor),
        triangles: mask.triangles.map(([a, b, c]) => [
          transform(mask.node, a),
          transform(mask.node, b),
          transform(mask.node, c),
        ]),
        rules: {
          mask_type:
            (mask.characterBoundary ? 1 : 0) |
            (mask.projectileBoundary || mask.obstacles.length ? 2 : 0) |
            (mask.view ? 4 : 0) |
            (mask.obstacles.length ? 16 : 0),
          character_polyline: boundary(mask.characterBoundary, true, mask.characterBoundaryClosed),
          projectile_polyline:
            boundary(mask.projectileBoundary, false, mask.projectileBoundaryClosed) ??
            (mask.obstacles.length ? [] : null),
          obstacle_indices: mask.obstacles.map((id) => {
            const shape = partSight.get(id);
            if (!shape)
              throw new Error(
                `${placement.id}/${mask.id}: mask obstacle ${id} is hidden or missing`,
              );
            const index = sight.indexOf(shape);
            if (index > 65535) throw new Error("Mask obstacle reference exceeds 16-bit indices");
            return index;
          }),
        },
      });
    }
    const materialIndices = new Map<string, number>();
    for (const region of gameplay.materials ?? []) {
      const index = materials.length;
      materialIndices.set(region.id, index);
      if (index > 65535) throw new Error("Too many asset material regions");
      materials.push({
        material: region.material,
        polygon: {
          points: ring(
            region.polygon.map((p) => project(transform(region.node, p))),
            `${placement.id}/${region.id}`,
          ),
        },
      });
      if (region.ground) groundMaterials.push(index);
      for (const node of region.obstacles) {
        const obstacle = partSight.get(node);
        if (!obstacle)
          throw new Error(
            `${placement.id}/${region.id}: material obstacle ${node} is hidden or missing`,
          );
        obstacle.material_indices.push(index);
      }
    }
    const dynamic = (gameplay.movementTransitions ?? []).flatMap((t) => [
      ...t.initial.map((surface) => ({
        surface,
        transition: `${placement.id}/${t.id}`,
        applied: false,
      })),
      ...t.applied.map((surface) => ({
        surface,
        transition: `${placement.id}/${t.id}`,
        applied: true,
      })),
    ]);
    for (const t of gameplay.movementTransitions ?? []) {
      const sightRefs = (refs: string[] = []) =>
        refs.map((id) => {
          const shape = partSight.get(id);
          if (!shape)
            throw new Error(`${placement.id}/${t.id}: sight obstacle ${id} is hidden or missing`);
          return sight.indexOf(shape);
        });
      const contour = (points: Point[]) =>
        points.length
          ? ring(
              points.map((p) => project(transform(t.node, [...p, t.waypoint[2]]))),
              `${placement.id}/${t.id}`,
            )
          : [];
      transitions.push({
        id: `${placement.id}/${t.id}`,
        waypoint: transform(t.node, t.waypoint),
        waypointAnchor: transform(t.node, t.waypointAnchor ?? t.waypoint),
        active: t.active,
        definitive: t.definitive,
        applyPolygon: contour(t.applyPolygon),
        noApplyPolygon: contour(t.noApplyPolygon),
        changes: [],
        initialSight: sightRefs(t.initialSight),
        appliedSight: sightRefs(t.appliedSight),
        initialMasks: (t.initialMasks ?? []).map((id) => `${placement.id}/${id}`),
        appliedMasks: (t.appliedMasks ?? []).map((id) => `${placement.id}/${id}`),
        ...(t.doorLinks
          ? {
              doorLinks: {
                mode: t.doorLinks.mode,
                ids: t.doorLinks.ids.map((id) => `${placement.id}/${id}`),
              },
            }
          : {}),
      });
    }
    for (const surface of [
      ...gameplay.surfaces,
      ...(gameplay.movementBlockers ?? []),
      ...(gameplay.movementClearances ?? []),
      ...dynamic.map((d) => d.surface),
    ]) {
      const local = surface.polygon.map((p, i): Vec3 => [
        p[0],
        p[1],
        typeof surface.height === "number" ? surface.height : surface.height[i]!,
      ]);
      const localPlane = heightPlane(local);
      const points = local.map((p) => transform(surface.node, p));
      // Fit before integer quantization so height remains exact after placement.
      const plane = heightPlane(points.map(([x, y, z]) => [x, y - z, z]));
      const target = gameplay.movementClearances?.includes(surface)
        ? movementClearances
        : gameplay.movementBlockers?.includes(surface)
          ? movementBlockers
          : surfaces;
      const placed = {
        owner: placement.id,
        navigationRegion:
          surface.navigationRegion === undefined
            ? undefined
            : `${placement.id}/${surface.navigationRegion}`,
        polygon: ring(points.map(project), `${placement.id}/${surface.id}`),
        plane,
        ...(gameplay.lifts?.find((l) => l.surface === surface.id)
          ? { lift: `${placement.id}/${gameplay.lifts.find((l) => l.surface === surface.id)!.id}` }
          : {}),
        holes: (surface.holes ?? []).map((hole) =>
          ring(
            hole.map((p) =>
              project(transform(surface.node, [p[0], p[1], planeHeight(localPlane, p)])),
            ),
            `${placement.id}/${surface.id} hole`,
          ),
        ),
      };
      const change = dynamic.find((d) => d.surface === surface);
      if (gameplay.surfaces.includes(surface))
        projectionSupports.push({
          ...placed,
          footprint: surface.projectionMaterials?.footprint
            ? ring(
                surface.projectionMaterials.footprint.map((point): Point => {
                  const [x, y, z] = transform(surface.node, point);
                  return [x, y - z];
                }),
                `${placement.id}/${surface.id} receiving footprint`,
              )
            : undefined,
          defaultMaterial: surface.projectionMaterials?.defaultMaterial ?? 0,
          materialIndices: (surface.projectionMaterials?.regions ?? []).map((id) =>
            materialIndices.get(id)!,
          ),
          materialSignature: JSON.stringify(
            (surface.projectionMaterials?.regions ?? []).map(
              (id) => materials[materialIndices.get(id)!],
            ),
          ),
          explicit: surface.projectionMaterials !== undefined,
          tiePriority: surface.projectionMaterials?.priority ?? 0,
          priority: Math.fround(
            surface.projectionMaterials?.priorityHeight === undefined
              ? Math.max(...points.map((point) => point[2]))
              : transform(surface.node, [0, 0, surface.projectionMaterials.priorityHeight])[2],
          ),
        });
      if (change)
        transitionBlockers.push({
          ...placed,
          transition: change.transition,
          applied: change.applied,
        });
      else target.push(placed);
    }
    const placeDoor = (door: AssetGameplay["doors"][number], lift?: string, interior?: string) =>
      doors.push({
        lift,
        interior,
        name: `${placement.id}/${door.id}`,
        definition: door,
        outside: transform(door.node, door.outside),
        inside: transform(door.node, door.inside),
        outsideAnchor: transform(door.node, door.outsideAnchor ?? door.outside),
        insideAnchor: transform(door.node, door.insideAnchor ?? door.inside),
        middle: project(transform(door.node, door.middle)),
        polygon: door.polygon.length
          ? ring(
              door.polygon.map((p) => project(transform(door.node, [...p, door.outside[2]]))),
              `${placement.id}/${door.id} click polygon`,
            )
          : [],
      });
    for (const door of gameplay.doors) placeDoor(door);
    for (const lift of gameplay.lifts ?? []) {
      const id = `${placement.id}/${lift.id}`;
      const origin = transform(lift.node, [0, 0, 0]);
      const direction = transform(lift.node, [...lift.direction, 0]);
      const angle = Math.atan2(direction[0] - origin[0], origin[1] - direction[1]);
      lifts.push({
        id,
        type: lift.type,
        direction: (Math.round((angle * 8) / Math.PI) + 16) % 16,
        joins: (lift.joins ?? []).map((p) => transform(lift.node, p)),
      });
      for (const door of lift.doors) placeDoor(door, id);
    }
    for (const interior of gameplay.interiors ?? []) {
      const id = `${placement.id}/${interior.id}`;
      const origin = transform(interior.node, [0, 0, 0]);
      placedInteriors.push({
        id,
        joins: (interior.joins ?? []).map((join) => {
          const direction = transform(interior.node, [...join.direction, 0]);
          return {
            point: transform(interior.node, join.point),
            direction: [direction[0] - origin[0], direction[1] - origin[1]],
          };
        }),
      });
      for (const door of interior.doors) placeDoor(door, undefined, id);
    }
  }
  const interiorIdentities = assembleInteriors(placedInteriors);
  for (const door of doors)
    if (door.interior) door.interior = interiorIdentities.get(door.interior)!;
  // A disconnected passage with no entrance needs no runtime room.
  const interiors = [...new Set(interiorIdentities.values())].filter((id) =>
    doors.some((door) => door.interior === id),
  );
  const assembledLifts = assembleLiftSegments(lifts);
  const assembledJumps = assembleJumpSegments(jumpSegments);
  jumpPairs.push(...assembledJumps.pairs);
  for (const segment of assembledJumps.unmatched)
    warnings.push(
      `Jump ${segment.id}: no matching edge after placement; connection is unavailable.`,
    );
  lifts = assembledLifts.lifts;
  for (const surface of surfaces)
    if (surface.lift) surface.lift = assembledLifts.identities.get(surface.lift)!;
  for (const support of projectionSupports)
    if (support.lift) support.lift = assembledLifts.identities.get(support.lift)!;
  for (const door of doors) if (door.lift) door.lift = assembledLifts.identities.get(door.lift)!;
  if (!surfaces.length)
    throw new Error(
      "Assets define no walkable surfaces; a map rectangle is not a substitute for authored ground",
    );
  if (
    surfaces.some((s) =>
      s.polygon.some((p) => p[0] < 0 || p[1] < 0 || p[0] >= bounds[2] || p[1] >= bounds[3]),
    )
  )
    throw new Error("Export frame cuts authored walkable surfaces; enlarge it before compiling");
  const planes: HeightPlane[] = [];
  for (const surface of surfaces.filter((s) => !s.lift)) {
    if (!planes.some((p) => p.every((n, i) => Math.abs(n - surface.plane[i]!) < 1e-7)))
      planes.push(surface.plane);
  }
  planes.sort((a, b) => a[2] - b[2] || a[0] - b[0] || a[1] - b[1]);
  // Ordinary surfaces occupy conventional layers; all lifts use the reserved last layer.
  const layers: CompiledAssetGeometry["motion_data"]["layers"] = Array.from(
    { length: Math.max(1, planes.length) + 1 },
    () => [],
  );
  const groups = planes.flatMap((plane, layer) => {
    const matching = surfaces.filter(
      (s) => !s.lift && s.plane.every((n, i) => Math.abs(n - plane[i]!) < 1e-7),
    );
    return [...new Set(matching.map((s) => s.navigationRegion))].map((region) => ({
      plane,
      layer,
      lift: undefined as string | undefined,
      navigationRegion: region,
      surfaces: matching.filter((s) => s.navigationRegion === region),
    }));
  });
  for (const surface of surfaces.filter((s) => s.lift))
    groups.push({
      plane: surface.plane,
      layer: layers.length - 1,
      lift: surface.lift,
      navigationRegion: undefined,
      surfaces: [surface],
    });
  const areas: {
    plane: HeightPlane;
    lift?: string;
    sector: number;
    layer: number;
    polygon: Point[];
    blockers: Point[][];
  }[] = [];
  let sector = 0;
  const navigationPieces: NavigationPiece[] = [];
  for (const { layer, plane, lift, navigationRegion, surfaces: group } of groups) {
    const input = group.map((s): Polygon => [
      polygon(s.polygon)[0]!,
      ...s.holes.map((h) => polygon(h)[0]!),
    ]);
    let merged = polygonClipping.union(input[0]!, ...input.slice(1));
    // Authored movement exclusions belong to a plane and follow their asset placement.
    // Subtract whole polygons so holes in blockers remain walkable islands.
    for (const blocker of movementBlockers) {
      if (!plane.every((n, i) => Math.abs(n - blocker.plane[i]!) < 1e-7)) continue;
      merged = polygonClipping.difference(merged, [
        polygon(blocker.polygon)[0]!,
        ...blocker.holes.map((h) => polygon(h)[0]!),
      ]);
    }
    // Intersect solids with this surface's plane in world XY, then project
    // the resulting slice. Bounding-box clipping also handles concave solids.
    const worldPlane = heightPlane(
      group[0]!.polygon.map(([x, y]) => {
        const z = planeHeight(plane, [x, y]);
        return [x, y + z, z];
      }),
    );
    for (const { owner, shape: obstacle } of movementSolids) {
      if (!obstacle.solid) continue;
      const footprint = obstacle.points.map((p): Point => [p.x, p.y]);
      const top = heightPlane(
        obstacle.points.map((p) => [p.x, p.y, p.z_top]),
        false,
      );
      const bottom = heightPlane(
        obstacle.points.map((p) => [p.x, p.y, p.z_bottom]),
        false,
      );
      const xs = footprint.map((p) => p[0]),
        ys = footprint.map((p) => p[1]);
      let slice: Point[] = [
        [Math.min(...xs), Math.min(...ys)],
        [Math.max(...xs), Math.min(...ys)],
        [Math.max(...xs), Math.max(...ys)],
        [Math.min(...xs), Math.max(...ys)],
      ];
      const above = top.map((n, i) => n - worldPlane[i]!) as HeightPlane;
      if (footprint.every((p) => planeHeight(above, p) <= 1e-7)) continue;
      slice = clipHeight(slice, above);
      slice = clipHeight(slice, worldPlane.map((n, i) => n - bottom[i]!) as HeightPlane);
      if (slice.length < 3 || Math.abs(signedArea(slice)) < 1e-7) continue;
      const cuts = fixedPolygonBoolean("intersection", polygon(footprint), [polygon(slice)]);
      for (const cut of cuts) {
        const projected: Polygon = cut.map((r) =>
          r.map(([x, y]) => [x, y - planeHeight(worldPlane, [x, y])]),
        );
        let regions = [projected];
        for (const clearance of movementClearances) {
          if (
            clearance.owner !== owner ||
            !plane.every((n, i) => Math.abs(n - clearance.plane[i]!) < 1e-7)
          )
            continue;
          regions = polygonClipping.difference(regions, [
            polygon(clearance.polygon)[0]!,
            ...clearance.holes.map((h) => polygon(h)[0]!),
          ]);
        }
        if (regions.length) merged = polygonClipping.difference(merged, regions);
      }
    }
    for (const poly of merged.flatMap((region) =>
      normalizeGeneratedMotion([region], `Movement layer ${layer}`, warnings),
    )) {
      const quantized = quantizeGeneratedMotionPolygon(
        poly,
        quantize,
        `Movement layer ${layer}`,
        warnings,
      );
      if (!quantized) continue;
      const boundary = ring(quantized[0]!, `Merged movement boundary on layer ${layer}`);
      const blockers = quantized
        .slice(1)
        .map((r) => ring(r, `Merged movement hole on layer ${layer}`));
      navigationPieces.push({ layer, plane, lift, navigationRegion, polygon: boundary, blockers });
    }
  }
  for (const region of assembleNavigationRegions(navigationPieces, warnings)) {
    const { layer, lift, polygon: boundary, blockers, pieces } = region;
    const plane = pieces[0]!.plane;
    const changing = compileTransitionObstacles(
      boundary,
      blockers,
      plane,
      transitionBlockers,
      warnings,
      pieces.length > 1 ? pieces : undefined,
    );
    if (lift && changing.pairs.size)
      throw new Error(
        `Lift ${lift}: changing traversal surfaces require lift state compilation support`,
      );
    for (const [id, pair] of changing.pairs)
      transitions
        .find((t) => t.id === id)!
        .changes.push({
          layer,
          sector,
          changing_obstacle: pair,
        });
    layers[layer]!.push({
      is_lift: !!lift,
      state_id: 0,
      polygon: { points: boundary },
      skeleton_segments: [],
      flags: 0,
      obstacles: [
        ...blockers.map((points) => ({ state_id: 0, polygon: { points } })),
        ...changing.obstacles,
      ],
    });
    // Projection surfaces provide layer-aware elevation and picking.
    for (const piece of pieces) {
      areas.push({ ...piece, sector, layer, blockers: [...piece.blockers, ...changing.initial] });
      for (const material of partitionProjectionMaterials(
        piece.polygon,
        projectionSupports.filter(
          (support) =>
            support.lift === piece.lift &&
            support.navigationRegion === piece.navigationRegion &&
            support.plane.every((n, i) => Math.abs(n - piece.plane[i]!) < 1e-7),
        ),
        warnings,
      )) {
        if (!lift && !material.explicit && !piece.plane.some((n) => Math.abs(n) > 1e-7)) continue;
        sight.push({
          points: material.polygon.map(([x, y]) => {
            const height = planeHeight(piece.plane, [x, y]);
            return { x, y: y + height, z_bottom: height, z_top: height };
          }),
          projection_area: [sector, layer],
          opaque: false,
          solid: false,
          mouse: true,
          show_shadow_polygon: false,
          default_material: material.defaultMaterial,
          material_indices: material.materialIndices,
        });
      }
    }
    sector += 1 + blockers.length + changing.obstacles.length;
  }
  const resolve = (point: Vec3, label: string, lift?: string | null, allowBlocked = false) => {
    const matches = areas.filter(
      (a) =>
        (lift === null || a.lift === lift) &&
        Math.abs(planeHeight(a.plane, [point[0], point[1] - point[2]]) - point[2]) < 1e-4 &&
        inside(project(point), a.polygon) &&
        (allowBlocked || !a.blockers.some((b) => inside(project(point), b))),
    );
    if (new Set(matches.map((a) => a.sector)).size !== 1) {
      const containing = areas.filter((a) => inside(project(point), a.polygon));
      const details = containing.slice(0, 8).map((a) => ({
        sector: a.sector,
        layer: a.layer,
        lift: a.lift,
        height: planeHeight(a.plane, [point[0], point[1] - point[2]]),
        blocked: a.blockers.some((b) => inside(project(point), b)),
      }));
      throw new Error(
        `${label} must resolve to exactly one ${allowBlocked ? "" : "unblocked "}walkable surface (found ${matches.length}); world point ${JSON.stringify(point)}, projected ${JSON.stringify(project(point))}; containing areas (${containing.length}, showing up to 8) ${JSON.stringify(details)}`,
      );
    }
    return matches[0]!;
  };
  const masks: NonNullable<CompiledAssetGeometry["masks"]> = [];
  const maskIndices = new Map<string, number[]>();
  for (const mask of placedMasks) {
    const layer = resolve(mask.anchor, `${mask.id} receiving anchor`, null, true).layer;
    const tiles = rasterizeMaskGeometry(mask.triangles, { ...mask.rules, layer });
    maskIndices.set(
      mask.id,
      tiles.map((_, index) => masks.length + index),
    );
    masks.push(...tiles);
  }
  if (masks.length > 65536) throw new Error("Too many compiled mask tiles");
  const maskRefs = (ids: string[]) =>
    ids.flatMap((id) => {
      const indices = maskIndices.get(id);
      if (!indices) throw new Error(`Unresolved transition mask ${id}`);
      return indices;
    });
  // Detached edges have no runtime connection. Retain zones used by any remaining pair.
  const usedJumpZones = new Set(jumpPairs.flatMap((pair) => pair.edges.map((edge) => edge.zone)));
  const activeJumpZones = jumpZones.filter((zone) => usedJumpZones.has(zone.id));
  const compiledJumpZones = activeJumpZones.map((zone) => {
    const area = resolve(zone.anchor, `${zone.id} landing anchor`);
    return {
      polygon: { points: zone.polygon },
      sector: area.sector,
      layer: area.layer,
      helper_needed: zone.helper,
    };
  });
  const compiledJumpPairs = jumpPairs.map((pair) => {
    const indices = pair.edges.map((edge) =>
      activeJumpZones.findIndex((zone) => zone.id === edge.zone),
    );
    const lines = pair.edges.map((edge, i) => {
      // Edge heights are authored independently of the receiving surface's plane.
      // In particular, integer edge heights need not equal fractional projection heights.
      const a: Vec3 = [...project(edge.a), quantize(edge.a[2])];
      const b: Vec3 = [...project(edge.b), quantize(edge.b[2])];
      if (a[0] === b[0] && a[1] === b[1])
        throw new Error(`${pair.id}: jump edge collapses on the movement grid`);
      return { point_a: a, point_b: b, jump_zone_index: indices[1 - i]! };
    });
    return { line1: lines[0]!, line2: lines[1]!, jump_long: pair.long };
  });
  // Runtime construction order is motion, materials, projection planes, then buildings.
  // Motion adds an out-of-map sector; each door also consumes a constructor slot.
  let nextInteriorSector =
    sector + 1 + materials.length + sight.filter((o) => o.projection_area !== null).length;
  const interiorAreas = new Map(
    interiors.map((id) => {
      const area = { sector: nextInteriorSector, layer: layers.length - 1 };
      nextInteriorSector += 1 + doors.filter((d) => d.interior === id).length;
      return [id, area] as const;
    }),
  );
  const omittedDoors = new Set<string>();
  const compiledDoors = doors.map((door) => {
    // Ordinary passages can meet traversal surfaces; lift doors retain their explicit owner.
    const outside = resolve(
        door.outsideAnchor,
        `${door.name} outside`,
        door.lift ? undefined : null,
      ),
      inside = door.interior
        ? interiorAreas.get(door.interior)!
        : resolve(door.insideAnchor, `${door.name} inside`, door.lift ?? null);
    if (outside.sector === inside.sector) {
      if (
        !door.definition.allowContinuous ||
        transitions.some((t) => t.doorLinks?.ids.includes(door.name))
      )
        throw new Error(`${door.name} does not connect distinct motion areas`);
      omittedDoors.add(door.name);
      warnings.push(
        `${door.name}: omitted unrestricted passage because both endpoints now share a movement area`,
      );
      return null;
    }
    const d = door.definition;
    return {
      door_type: d.type,
      active: d.active ?? true,
      locked_pc: d.locked,
      unlockable: d.unlockable,
      locked_npc_villain: d.lockedVillains ?? false,
      locked_npc_civilian: d.lockedCivilians ?? false,
      locked_pc_after_patch: d.afterTransition?.locked ?? d.locked,
      unlockable_after_patch: d.afterTransition?.unlockable ?? d.unlockable,
      locked_npc_villain_after_patch:
        d.afterTransition?.lockedVillains ?? d.lockedVillains ?? false,
      locked_npc_civilian_after_patch:
        d.afterTransition?.lockedCivilians ?? d.lockedCivilians ?? false,
      door_sector: { points: door.polygon },
      point_out: project(door.outside),
      sector_out: outside.sector,
      layer_out: outside.layer,
      point_mid: door.middle,
      point_in: project(door.inside),
      sector_in: inside.sector,
      layer_in: inside.layer,
    };
  });
  const selectDoors = (predicate: (door: (typeof doors)[number]) => boolean) =>
    compiledDoors.flatMap((compiled, i) => (compiled && predicate(doors[i]!) ? [compiled] : []));
  // Native non-lift door allocation follows interiors, then standalone passages.
  const patchDoors = [
    ...interiors.flatMap((id) => doors.filter((door) => door.interior === id)),
    ...doors.filter((door) => !door.lift && !door.interior),
  ].filter((door) => !omittedDoors.has(door.name));
  const doorIndices = new Map(patchDoors.map((door, index) => [door.name, index]));
  return {
    ...(warnings.length ? { warnings } : {}),
    motion_data: { layers, graph_bytes: [] },
    ...(masks.length ? { masks } : {}),
    ...(compiledJumpZones.length
      ? { jump_zones: compiledJumpZones, jump_line_pairs: compiledJumpPairs }
      : {}),
    ...(lights.length
      ? {
          light_sectors: lights.flatMap((light) => {
            if (light.receivers) {
              const layers = new Set(
                light.receivers.map((point, index) => {
                  if (!inside(project(point), light.polygon))
                    throw new Error(
                      `${light.id}: receiver ${index} lies outside the light contour`,
                    );
                  return resolve(point, `${light.id} receiver ${index}`, null, true).layer;
                }),
              );
              return [...layers].map((layer) => ({
                layer,
                polygon: { points: light.polygon },
                ambience: light.ambiences,
              }));
            }
            const matchingLayers = new Set(
              areas
                .filter(
                  (area) =>
                    area.plane.every((n, i) => Math.abs(n - light.plane[i]!) < 1e-7) &&
                    polygonClipping.intersection([area.polygon], [light.polygon]).length > 0,
                )
                .map((area) => area.layer),
            );
            if (matchingLayers.size !== 1)
              throw new Error(
                `${light.id}: light region must overlap exactly one receiving layer (found ${matchingLayers.size})`,
              );
            return {
              layer: [...matchingLayers][0]!,
              polygon: { points: light.polygon },
              ambience: light.ambiences,
            };
          }),
        }
      : {}),
    ...(transitions.length
      ? {
          movement_transitions: transitions.map((t) => {
            if (
              !t.changes.length &&
              !t.initialSight.length &&
              !t.appliedSight.length &&
              !t.initialMasks.length &&
              !t.appliedMasks.length &&
              !t.doorLinks
            )
              throw new Error(`${t.id}: movement transition affects no walkable area`);
            // State reference points identify a surface even inside its collision contours.
            // Door receiving anchors and jump landing anchors require an unblocked position.
            const area = resolve(t.waypointAnchor, `${t.id} waypoint`, undefined, true);
            return {
              id: t.id,
              waypoint: project(t.waypoint),
              sector: area.sector,
              layer: area.layer,
              active: t.active,
              definitive: t.definitive,
              apply_polygon: { points: t.applyPolygon },
              no_apply_polygon: { points: t.noApplyPolygon },
              motion_changes: t.changes,
              ...(t.initialSight.length ? { initial_sight: t.initialSight } : {}),
              ...(t.appliedSight.length ? { applied_sight: t.appliedSight } : {}),
              ...(t.initialMasks.length ? { initial_masks: maskRefs(t.initialMasks) } : {}),
              ...(t.appliedMasks.length ? { applied_masks: maskRefs(t.appliedMasks) } : {}),
              ...(t.doorLinks
                ? {
                    door_links: {
                      mode: t.doorLinks.mode,
                      indices: t.doorLinks.ids.map((id) => {
                        const index = doorIndices.get(id);
                        if (index === undefined || index > 65535)
                          throw new Error(`${t.id}: unresolved transition door ${id}`);
                        return index;
                      }),
                    },
                  }
                : {}),
            };
          }),
        }
      : {}),
    ...(mapSettings ? { map_settings: mapSettings } : {}),
    ...(sounds.length ? { sound_sources: sounds } : {}),
    sight_obstacles: sight,
    ...(materials.length
      ? { material_sectors: materials, sight_material_indices: groundMaterials }
      : {}),
    doors: selectDoors((door) => !door.lift && !door.interior),
    ...(interiors.length
      ? {
          buildings: interiors.map((id) => ({
            Building: {
              doors: selectDoors((door) => door.interior === id),
            },
          })),
        }
      : {}),
    ...(lifts.length
      ? {
          lifts: lifts.map((lift) => {
            const area = areas.find((a) => a.lift === lift.id);
            if (!area) throw new Error(`Missing lift motion area ${lift.id}`);
            const endpoints = selectDoors((door) => door.lift === lift.id);
            if (endpoints.length < 2 || !endpoints.some((d) => d.door_type === 5))
              throw new Error(
                `Lift ${lift.id} needs at least two traversal doors including a low door`,
              );
            if (new Set(endpoints.map((d) => d.point_out[1])).size < 2)
              throw new Error(
                `Lift ${lift.id} needs distinct projected endpoint heights after placement`,
              );
            return {
              motion_area_index: area.sector,
              lift_type: lift.type,
              direction: lift.direction,
              doors: endpoints,
            };
          }),
        }
      : {}),
  };
}
