import polygonClipping, { type Polygon } from "polygon-clipping";
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

type Instance = {
  id: string;
  descriptor: GameplayAssetDescriptor;
  parts: Map<string, Level3DObject>;
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
      instance = { id, descriptor, parts: new Map(), background: false };
      result.set(id, instance);
    }
    if (instance.parts.has(match[2]!))
      throw new Error(`Duplicate asset node ${part.node} in placement ${id}`);
    instance.parts.set(match[2]!, part);
  }
  for (const source of document.sceneAssets) {
    if (source.role !== "ground") continue;
    const descriptor = descriptors.get(source.id);
    if (!descriptor) throw new Error(`Ground asset ${source.id} has no pinned gameplay definition`);
    result.set(`ground/${source.id}`, {
      id: `ground/${source.id}`,
      descriptor,
      parts: new Map(),
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
  }[] = [];
  const movementBlockers: typeof surfaces = [];
  const movementSolids: { owner: string; shape: SightObstacle }[] = [];
  const movementClearances: typeof surfaces = [];
  const lifts: { id: string; type: number; direction: number }[] = [];
  const interiors: string[] = [];
  const doors: {
    name: string;
    lift?: string;
    interior?: string;
    definition: AssetGameplay["doors"][number];
    outside: Vec3;
    inside: Vec3;
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
        const part = placement.parts.get(node);
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
    if (gameplay.collision === "parts")
      for (const [node, part] of placement.parts) {
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
        if (gameplay.movementBlockers === undefined)
          movementSolids.push({ owner: placement.id, shape: sight.at(-1)! });
      }
    for (const region of gameplay.materials ?? []) {
      const index = materials.length;
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
    for (const surface of [
      ...gameplay.surfaces,
      ...(gameplay.movementBlockers ?? []),
      ...(gameplay.movementClearances ?? []),
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
      target.push({
        owner: placement.id,
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
      });
    }
    const placeDoor = (door: AssetGameplay["doors"][number], lift?: string, interior?: string) =>
      doors.push({
        lift,
        interior,
        name: `${placement.id}/${door.id}`,
        definition: door,
        outside: transform(door.node, door.outside),
        inside: transform(door.node, door.inside),
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
      lifts.push({ id, type: lift.type, direction: (Math.round((angle * 8) / Math.PI) + 16) % 16 });
      for (const door of lift.doors) placeDoor(door, id);
    }
    for (const interior of gameplay.interiors ?? []) {
      const id = `${placement.id}/${interior.id}`;
      interiors.push(id);
      for (const door of interior.doors) placeDoor(door, undefined, id);
    }
  }
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
  const groups = planes.map((plane, layer) => ({
    plane,
    layer,
    lift: undefined as string | undefined,
    surfaces: surfaces.filter(
      (s) => !s.lift && s.plane.every((n, i) => Math.abs(n - plane[i]!) < 1e-7),
    ),
  }));
  for (const surface of surfaces.filter((s) => s.lift))
    groups.push({
      plane: surface.plane,
      layer: layers.length - 1,
      lift: surface.lift,
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
  for (const { layer, plane, lift, surfaces: group } of groups) {
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
      const cuts = polygonClipping.intersection(polygon(footprint), polygon(slice));
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
    const output = layers[layer]!;
    for (const poly of merged) {
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
      const area = { plane, lift, sector, layer, polygon: boundary, blockers };
      areas.push(area);
      sector += 1 + blockers.length;
      output.push({
        is_lift: !!lift,
        state_id: 0,
        polygon: { points: boundary },
        skeleton_segments: [],
        flags: 0,
        obstacles: blockers.map((points) => ({ state_id: 0, polygon: { points } })),
      });
      // Projection surfaces provide layer-aware elevation and picking.
      if (lift || plane.some((n) => Math.abs(n) > 1e-7))
        sight.push({
          points: boundary.map(([x, y]) => {
            const height = planeHeight(plane, [x, y]);
            return { x, y: y + height, z_bottom: height, z_top: height };
          }),
          projection_area: [area.sector, layer],
          opaque: false,
          solid: false,
          mouse: true,
          show_shadow_polygon: false,
          default_material: 0,
          material_indices: [],
        });
    }
  }
  const resolve = (point: Vec3, label: string, lift?: string) => {
    const matches = areas.filter(
      (a) =>
        a.lift === lift &&
        Math.abs(planeHeight(a.plane, [point[0], point[1] - point[2]]) - point[2]) < 1e-4 &&
        inside(project(point), a.polygon) &&
        !a.blockers.some((b) => inside(project(point), b)),
    );
    if (matches.length !== 1) {
      const containing = areas.filter((a) => inside(project(point), a.polygon));
      const details = containing.slice(0, 8).map((a) => ({
        sector: a.sector,
        layer: a.layer,
        lift: a.lift,
        height: planeHeight(a.plane, [point[0], point[1] - point[2]]),
        blocked: a.blockers.some((b) => inside(project(point), b)),
      }));
      throw new Error(
        `${label} must resolve to exactly one unblocked walkable surface (found ${matches.length}); world point ${JSON.stringify(point)}, projected ${JSON.stringify(project(point))}; containing areas (${containing.length}, showing up to 8) ${JSON.stringify(details)}`,
      );
    }
    return matches[0]!;
  };
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
  const compiledDoors = doors.map((door) => {
    const outside = resolve(door.outside, `${door.name} outside`),
      inside = door.interior
        ? interiorAreas.get(door.interior)!
        : resolve(door.inside, `${door.name} inside`, door.lift);
    if (outside.sector === inside.sector)
      throw new Error(`${door.name} does not connect distinct motion areas`);
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
  return {
    ...(warnings.length ? { warnings } : {}),
    motion_data: { layers, graph_bytes: [] },
    ...(mapSettings ? { map_settings: mapSettings } : {}),
    ...(sounds.length ? { sound_sources: sounds } : {}),
    sight_obstacles: sight,
    ...(materials.length
      ? { material_sectors: materials, sight_material_indices: groundMaterials }
      : {}),
    doors: compiledDoors.filter((_, i) => !doors[i]!.lift && !doors[i]!.interior),
    ...(interiors.length
      ? {
          buildings: interiors.map((id) => ({
            Building: {
              doors: compiledDoors.filter((_, i) => doors[i]!.interior === id),
            },
          })),
        }
      : {}),
    ...(lifts.length
      ? {
          lifts: lifts.map((lift) => {
            const area = areas.find((a) => a.lift === lift.id);
            if (!area) throw new Error(`Missing lift motion area ${lift.id}`);
            const endpoints = compiledDoors.filter((_, i) => doors[i]!.lift === lift.id);
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
