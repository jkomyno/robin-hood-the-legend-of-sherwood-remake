/** One-time authoring migration. Never imported by the editor's map compiler. */
import fs from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import polygonClipping, { type Polygon, type MultiPolygon } from "polygon-clipping";
import {
  gameToScene,
  sceneToGame,
  partMatrix,
  transformedObstacle,
  type Level3DObject,
  type Vec3,
  type Point,
  type ProtoLevel,
} from "@rle/shared";
import { recoverEndpointElevation, distanceToPolygon } from "./recovery-elevation.ts";
import { readStoredMap, pinnedDescriptors } from "./stored-map.ts";
import { recoverGroundGameplay, polygonArea } from "./recover-ground-gameplay.ts";
import {
  recoveredGameplayDefinition,
  descriptorGameplayPacket,
  type RecoveredGameplayPacket,
} from "./recovered-gameplay-definition.ts";
import type { AssetGameplay, GameplayAssetDescriptor } from "../../shared/src/asset-gameplay.ts";
import { diagnoseGameplayCandidates } from "./diagnose-gameplay-candidates.ts";
import { quantizeRecoveredMotion } from "./quantize-recovered-motion.ts";
import { recoverSoundSource, containsSoundPolyline } from "./recover-sound-source.ts";
import { recoverLightPlane, recoverLightRegion } from "./recover-light-region.ts";
import { recoverJumpGeometry, recoverJumpSegment } from "./recover-jump-geometry.ts";
import { terrainOwnsJump } from "./terrain-jump-ownership.ts";
import { jumpEdgeOwners } from "./jump-edge-ownership.ts";
import { recoverMotionStates } from "./recover-motion-states.ts";
import { recoverMovementTransition } from "./recover-movement-transition.ts";
import { recoverLiftJoins } from "./recover-lift-joins.ts";
import {
  nonrenderingGameplayOwners,
  type GameplayOwnershipCatalog,
} from "./nonrendering-gameplay-owners.ts";
import { recoveryDoorGroups } from "./recovery-door-groups.ts";
import { doorOwnershipFootprint, recoverDoorStateOwner } from "./recover-door-owner.ts";
import { quantizeGeneratedMotionPolygon } from "../../shared/src/motion-quantization.ts";
import { partitionRecoverySurfaces } from "./recovery-surface-partition.ts";
import { recoverSurfaceOwners } from "./recovery-surface-owners.ts";
import { recoverMovementClearance } from "./recover-movement-clearance.ts";
import {
  heightPlane as fitHeightPlane,
  planeHeight as evaluateHeight,
  type HeightPlane,
} from "../../shared/src/gameplay-plane.ts";

const { values } = parseArgs({
  options: {
    map: { type: "string" },
    library: { type: "string", default: "../library" },
    source: { type: "string" },
    out: { type: "string" },
    ownership: { type: "string" },
  },
});
if (!values.map || !values.source || !values.out)
  throw new Error(
    "Usage: --map <saved-map.json> --library <library> --source <proto-level.json> --out <authoring directory>",
  );
const document = await readStoredMap(values.map, values.library);
const descriptors = await pinnedDescriptors(
  values.library,
  document.assetSources ?? [],
  document.sceneAssets,
);
const proto: ProtoLevel = JSON.parse(await fs.readFile(values.source, "utf8"));
const locals = new Map<
  number,
  {
    asset: string;
    node: string;
    part: Level3DObject;
    collisionId?: string;
    sourceShape?: ProtoLevel["sight_obstacles"][number];
  }[]
>();
for (const part of document.objects) {
  const match = /^asset:([^:]+):(.+)$/.exec(part.node);
  if (!match || part.source.obstacle === undefined) continue;
  const list = locals.get(part.source.obstacle) ?? [];
  if (!list.some((item) => item.asset === match[1] && item.node === match[2]))
    list.push({ asset: match[1]!, node: match[2]!, part });
  locals.set(part.source.obstacle, list);
}
const packets = new Map<
  string,
  RecoveredGameplayPacket & {
    version: 1;
    status: "needs-review";
    issues: string[];
    gameplayCandidate?: AssetGameplay;
  }
>();
const packet = (asset: string) => {
  let p = packets.get(asset);
  if (!p) {
    p = {
      version: 1,
      status: "needs-review",
      asset,
      surfaces: [],
      connections: [],
      issues: [],
    };
    packets.set(asset, p);
  }
  return p;
};
for (const descriptor of descriptors.values()) {
  if (descriptor.editor_usage === "map-background") continue;
  Object.assign(packet(descriptor.id), descriptorGameplayPacket(descriptor));
  packet(descriptor.id).issues.push(
    "Geometry seeded from asset parts; verify recovered movement clearances and feature coverage before publication",
  );
  if (descriptor.parts.some((p) => p.mission_profile))
    packet(descriptor.id).issues.push(
      "Mission-authored geometry retained; recover associated state transitions and behaviours separately",
    );
}
const localize = (part: Level3DObject, point: Vec3): Vec3 => {
  const m = partMatrix(document.camera, document, part),
    p = gameToScene(document.camera, ...point);
  const offset = p.map((v, i) => v - m[12 + i]!) as Vec3;
  // Placement transforms are rigid in the scene frame; transpose the rotation.
  const local = [0, 1, 2].map(
    (col) => m[col * 4]! * offset[0] + m[col * 4 + 1]! * offset[1] + m[col * 4 + 2]! * offset[2],
  ) as Vec3;
  return sceneToGame(document.camera, local);
};
const close = (points: Point[]): Polygon => [[...points, points[0]!]];
const planeHeight = (
  points: ProtoLevel["sight_obstacles"][number]["points"],
  x: number,
  y: number,
) => {
  points = points.map((p) => ({ ...p, y: p.y - p.z_top }));
  const a = points[0]!;
  for (let i = 1; i + 1 < points.length; i++) {
    const b = points[i]!,
      c = points[i + 1]!,
      det = (b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y);
    if (Math.abs(det) < 1e-6) continue;
    const dx = ((b.z_top - a.z_top) * (c.y - a.y) - (c.z_top - a.z_top) * (b.y - a.y)) / det;
    const dy = ((b.x - a.x) * (c.z_top - a.z_top) - (c.x - a.x) * (b.z_top - a.z_top)) / det;
    return a.z_top + (x - a.x) * dx + (y - a.y) * dy;
  }
  throw new Error("Projection surface has no valid plane");
};
const unresolved: unknown[] = [];
const ownershipPath =
  values.ownership ??
  new URL(
    `../../refinement/catalogs/${encodeURIComponent((document.sourceMap ?? path.basename(values.source).replace(/\.rhp\.json$/i, "")).toLowerCase())}.json`,
    import.meta.url,
  );
let ownership: GameplayOwnershipCatalog | undefined;
try {
  ownership = JSON.parse(await fs.readFile(ownershipPath, "utf8"));
} catch (error) {
  if (values.ownership || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
}
if (ownership)
  for (const entry of nonrenderingGameplayOwners(ownership, locals)) {
    if (locals.has(entry.source)) continue;
    if (!entry.owner) {
      unresolved.push({ kind: "nonrendering-owner", ...entry });
      continue;
    }
    const source = proto.sight_obstacles[entry.source];
    if (!source) throw new Error(`Missing non-rendering gameplay volume ${entry.source}`);
    const owner = entry.owner;
    const id = `gameplay-volume-${entry.source}`;
    const { projection_area: _projection, material_indices: _materials, ...flags } = source;
    const shape = {
      ...flags,
      points: source.points.map((p) => {
        const bottom = localize(owner.part, [p.x, p.y, p.z_bottom]);
        const top = localize(owner.part, [p.x, p.y, p.z_top]);
        if (Math.hypot(bottom[0] - top[0], bottom[1] - top[1]) > 1e-5)
          throw new Error(
            `Non-rendering gameplay volume ${entry.source} needs a vertical owner frame`,
          );
        return { x: top[0], y: top[1], z_bottom: bottom[2], z_top: top[2] };
      }),
    };
    (packet(owner.asset).volumes ??= []).push({ id, node: owner.node, shape });
    locals.set(entry.source, [{ ...owner, collisionId: id, sourceShape: source }]);
    packet(owner.asset).issues.push(
      `Non-rendering gameplay restored from explicit ownership: ${entry.declaredOwner}`,
    );
  }
const coverage: unknown[] = [];
const movementStateInventory: {
  sector: number;
  layer: number;
  transitions: ReturnType<typeof recoverMotionStates>["transitions"];
}[] = [];
const groundAreas: Parameters<typeof recoverGroundGameplay>[0] = [];
const groundAreaSectors = new Set<number>();
let transferredGroundExclusions: MultiPolygon = [];
const clearanceSources: { regions: MultiPolygon; plane: HeightPlane }[] = [];
const groundProjectionOwners: {
  asset: string;
  node: string;
  part: Level3DObject;
  footprint: Point[];
}[] = [];
let sector = 0;
for (const [layer, areas] of proto.motion_data.layers.entries())
  for (const rawMotion of areas) {
    const identity = sector;
    sector += 1 + rawMotion.obstacles.length;
    const { base: motion, transitions } = recoverMotionStates(
      rawMotion,
      identity,
      layer,
      proto.patches,
    );
    if (transitions.length) {
      movementStateInventory.push({ sector: identity, layer, transitions });
    }
    const supports = proto.sight_obstacles.flatMap((obstacle, index) =>
      Array.isArray(obstacle.projection_area) &&
      obstacle.projection_area[0] === identity &&
      obstacle.projection_area[1] === layer
        ? [{ obstacle, index }]
        : [],
    );
    if (layer === 0 && supports.length) {
      const raised = supports.filter(({ obstacle }) =>
        obstacle.points.some((p) => Math.abs(p.z_top) > 1e-4),
      );
      if (
        !motion.is_lift &&
        motion.state_id === 0 &&
        motion.obstacles.every((o) => o.state_id === 0) &&
        raised.every(({ index }) => locals.get(index)?.length === 1)
      ) {
        const exclusions = raised.map(({ obstacle, index }) => {
          const footprint = obstacle.points.map((p): Point => [p.x, p.y - p.z_top]);
          groundProjectionOwners.push({ ...locals.get(index)![0]!, footprint });
          return { polygon: { points: footprint } };
        });
        groundAreas.push({
          polygon: motion.polygon,
          obstacles: [...motion.obstacles, ...exclusions],
        });
        groundAreaSectors.add(identity);
      } else {
        unresolved.push({
          kind: "terrain-projection-remainder",
          sector: identity,
          layer,
          reason: "Ground remainder requires static geometry and unique projection-surface owners",
        });
      }
    }
    if (!supports.length) {
      if (
        layer === 0 &&
        !motion.is_lift &&
        motion.state_id === 0 &&
        motion.obstacles.every((o) => o.state_id === 0)
      ) {
        groundAreas.push(motion);
        groundAreaSectors.add(identity);
        clearanceSources.push({
          regions: motion.obstacles.length
            ? polygonClipping.difference(
                close(motion.polygon.points),
                ...motion.obstacles.map((o) => close(o.polygon.points)),
              )
            : [close(motion.polygon.points)],
          plane: [0, 0, 0],
        });
        continue;
      }
      unresolved.push({
        kind: "terrain-motion",
        sector: identity,
        layer,
        reason:
          "No projection-surface owner; separate terrain boundaries from placed-asset cutouts before authoring",
      });
      continue;
    }
    let recoveredArea = 0;
    let quantizationDifferenceArea = 0;
    // Preserve a continuous local walking region independently of its height planes.
    // Multi-asset ownership needs explicit joins; a shared label cannot cross placements.
    const supportOwners = supports.map(({ index }) => locals.get(index) ?? []);
    const soleOwner = supportOwners[0]?.[0]?.asset;
    const regionIsLocal =
      !motion.is_lift &&
      supports.length > 0 &&
      soleOwner !== undefined &&
      supportOwners.every((owners) => owners.length === 1 && owners[0]!.asset === soleOwner);
    const navigationRegion = regionIsLocal ? `walk-region-${identity}` : undefined;
    const partition = partitionRecoverySurfaces(
      close(motion.polygon.points),
      motion.obstacles.map((o) => close(o.polygon.points)),
      supports.map(({ obstacle }) => ({
        polygon: close(obstacle.points.map((p) => [p.x, p.y - p.z_top])),
        maximumHeight: Math.max(...obstacle.points.map((p) => Math.max(p.z_top, p.z_bottom))),
      })),
    );
    const staticMotion = motion.state_id === 0 && motion.obstacles.every((o) => o.state_id === 0);
    if (layer === 0 && staticMotion)
      clearanceSources.push({ regions: partition.ground, plane: [0, 0, 0] });
    for (const [supportIndex, { obstacle, index }] of supports.entries()) {
      const owners = locals.get(index) ?? [];
      if (!owners.length) {
        unresolved.push({
          kind: "surface-owner",
          sector: identity,
          layer,
          obstacle: index,
          candidates: owners.map((o) => o.asset),
        });
        continue;
      }
      let regions = polygonClipping.intersection(
        close(motion.polygon.points),
        close(obstacle.points.map((p) => [p.x, p.y - p.z_top])),
      );
      if (motion.obstacles.length)
        regions = polygonClipping.difference(
          regions,
          ...motion.obstacles.map((o) => close(o.polygon.points)),
        );
      if (staticMotion)
        clearanceSources.push({
          // Joined traversal planes share one movement area. Projection
          // priority must not carve collision seams between their supports.
          regions: motion.is_lift ? regions : partition.surfaces[supportIndex]!,
          plane: fitHeightPlane(
            obstacle.points.map((p) => [p.x, p.y - p.z_top, p.z_top]),
            false,
          ),
        });
      const overlapArea = polygonArea(regions) - polygonArea(partition.surfaces[supportIndex]!);
      if (overlapArea > 1e-6) {
        unresolved.push({
          kind: "projection-priority",
          sector: identity,
          layer,
          obstacle: index,
          overlapArea,
          reason:
            "Overlapping surfaces need placement-time priority; do not freeze another asset's footprint into this surface",
        });
      }
      let owned = [regions];
      if (owners.length > 1) {
        const split = recoverSurfaceOwners(
          regions,
          owners.map((owner) => {
            const definition = descriptors
              .get(owner.asset)!
              .parts.find((p) => p.node === owner.node);
            if (!definition?.obstacle_local_game) return [];
            const shape = transformedObstacle(document, {
              ...owner.part,
              obstacle: definition.obstacle_local_game,
            });
            return close(shape.points.map((p) => [p.x, p.y - p.z_top]));
          }),
          true,
        );
        owned = split.owned;
        for (const owner of owners) packet(owner.asset).issues.push(...split.warnings);
        coverage.push({
          kind: "split-surface-ownership",
          obstacle: index,
          candidates: owners.map((o) => ({ asset: o.asset, node: o.node })),
          unresolvedArea: split.unresolvedArea,
        });
        if (split.unresolvedArea > 1e-6)
          unresolved.push({
            kind: "surface-owner",
            sector: identity,
            layer,
            obstacle: index,
            unresolvedArea: split.unresolvedArea,
            candidates: owners.map((o) => o.asset),
          });
      }
      for (const [ownerIndex, owner] of owners.entries()) {
        for (const [regionIndex, generated] of owned[ownerIndex]!.entries()) {
          const region = quantizeGeneratedMotionPolygon(
            generated,
            Math.round,
            `${owner.node}-walk-${regionIndex}`,
            packet(owner.asset).issues,
          );
          quantizationDifferenceArea += region
            ? polygonArea(polygonClipping.xor(generated, region))
            : polygonArea([generated]);
          if (!region) continue;
          const points = region[0]!.slice(0, -1).map(([x, y]) => [x, y] as Point);
          recoveredArea += polygonArea([region]);
          const vertices = points.map(([x, y]) =>
            localize(owner.part, [
              x,
              y + planeHeight(obstacle.points, x, y),
              planeHeight(obstacle.points, x, y),
            ]),
          );
          packet(owner.asset).surfaces.push({
            id: `${owner.collisionId ?? owner.node}-walk-${regionIndex}`,
            node: owner.node,
            navigationRegion,
            vertices,
            kind: motion.is_lift ? "lift" : "walkable",
            holes: region
              .slice(1)
              .map((hole) =>
                hole
                  .slice(0, -1)
                  .map(([x, y]) =>
                    localize(owner.part, [
                      x,
                      y + planeHeight(obstacle.points, x, y),
                      planeHeight(obstacle.points, x, y),
                    ]),
                  ),
              ),
          });
          if (motion.is_lift)
            packet(owner.asset).issues.push(
              "Review lift surface coverage and endpoint ownership before publishing",
            );
        }
      }
    }
    coverage.push({
      sector: identity,
      layer,
      sourceArea: polygonArea(
        motion.obstacles.length
          ? polygonClipping.difference(
              close(motion.polygon.points),
              ...motion.obstacles.map((o) => close(o.polygon.points)),
            )
          : [close(motion.polygon.points)],
      ),
      recoveredArea,
      quantizationDifferenceArea,
      uncoveredArea: polygonArea(partition.ground),
    });
  }
if (groundAreas.length) {
  const grounds = document.sceneAssets.filter((s) => s.role === "ground");
  if (grounds.length !== 1) {
    unresolved.push({ kind: "terrain-owner", candidates: grounds.map((s) => s.id) });
  } else {
    const owners = [...locals]
      .flatMap(([index, candidates]) => {
        const obstacle = proto.sight_obstacles[index];
        if (
          candidates.length !== 1 ||
          !obstacle?.solid ||
          !obstacle.points.every((p) => p.z_bottom <= 0 && p.z_top > 0)
        )
          return [];
        return [{ ...candidates[0]!, footprint: obstacle.points.map((p): Point => [p.x, p.y]) }];
      })
      .concat(groundProjectionOwners);
    const ground = recoverGroundGameplay(groundAreas, owners);
    transferredGroundExclusions = ground.blockers.flatMap((b) => b.regions);
    const terrain = packet(grounds[0]!.id);
    terrain.issues.push(...ground.warnings);
    for (const section of ground.sections)
      for (const [index, region] of section.terrain.entries())
        terrain.surfaces.push({
          id: `${section.navigationRegion}-${index}`,
          navigationRegion: section.navigationRegion,
          node: "$root",
          kind: "walkable",
          vertices: region[0]!.slice(0, -1).map(([x, y]) => [x, y, 0]),
          holes: region.slice(1).map((hole) => hole.slice(0, -1).map(([x, y]) => [x, y, 0])),
        });
    for (const [index, blocker] of ground.blockers.entries()) {
      const owner = owners.find((o) => o.asset === blocker.asset && o.node === blocker.node)!;
      for (const [regionIndex, region] of blocker.regions.entries()) {
        const local = (ring: Point[]) =>
          ring.slice(0, -1).map(([x, y]) => localize(owner.part, [x, y, 0]));
        (packet(owner.asset).movementBlockers ??= []).push({
          id: `${owner.node}-ground-blocker-${index}-${regionIndex}`,
          node: owner.node,
          vertices: local(region[0]!),
          holes: region.slice(1).map(local),
        });
      }
      packet(owner.asset).issues.push(
        "Review movement contour ownership: footprint intersections can split exclusions shared by adjacent assets",
      );
    }
    terrain.issues.push(
      "Review residual terrain exclusions and asset coverage; geometric round-trip equality does not establish ownership",
    );
    coverage.push({
      kind: "ground-decomposition",
      sourceArea: ground.sourceArea,
      recoveredArea: ground.reconstructedArea,
      differenceArea: ground.differenceArea,
      coordinateGrid: ground.coordinateGrid,
      blockerOwners: ground.blockers.length,
      navigationRegions: ground.sections.map(({ navigationRegion, differenceArea }) => ({
        navigationRegion,
        differenceArea,
      })),
    });
  }
}
// Restore openings only in each placed asset's own derived collision. These
// local contours move with the asset; no assembled-map override is exported.
for (const [sourceIndex, source] of clearanceSources.entries()) {
  for (const owners of locals.values())
    for (const owner of owners) {
      if (packet(owner.asset).movementBlockers !== undefined) continue;
      const definition = descriptors.get(owner.asset)!.parts.find((p) => p.node === owner.node);
      const localObstacle = owner.sourceShape ?? definition?.obstacle_local_game;
      if (!localObstacle?.solid) continue;
      const solid =
        owner.sourceShape ??
        transformedObstacle(document, {
          ...owner.part,
          obstacle: localObstacle,
        });
      let regions: MultiPolygon;
      try {
        regions = recoverMovementClearance(source.regions, source.plane, solid, 1);
        regions = quantizeRecoveredMotion(
          regions,
          `${owner.node}-clearance-${sourceIndex}`,
          packet(owner.asset).issues,
        );
      } catch (error) {
        unresolved.push({
          kind: "movement-clearance",
          asset: owner.asset,
          node: owner.node,
          source: sourceIndex,
          error: String(error),
        });
        continue;
      }
      for (const [regionIndex, region] of regions.entries()) {
        const id = `${owner.node}-clearance-${sourceIndex}-${regionIndex}`;
        const local = (ring: Point[]) =>
          ring.slice(0, -1).map(([x, y]) => {
            const z = evaluateHeight(source.plane, [x, y]);
            return localize(owner.part, [x, y + z, z]);
          });
        (packet(owner.asset).movementClearances ??= []).push({
          id,
          node: owner.node,
          vertices: local(region[0]!),
          holes: region.slice(1).map(local),
        });
      }
    }
}
// Recover lifts only where their surface has a unique owner. Neighbour endpoints
// remain geometric queries; no source sector or layer indices enter asset packets.
const heightAt = (sector: number, layer: number, point: Point, projectionPoint = point) => {
  const supports = proto.sight_obstacles.filter(
    (o) =>
      Array.isArray(o.projection_area) &&
      o.projection_area[0] === sector &&
      o.projection_area[1] === layer,
  );
  return recoverEndpointElevation(
    supports.map((o) => ({
      distance: distanceToPolygon(
        projectionPoint,
        o.points.map((p) => [p.x, p.y - p.z_top]),
      ),
      height: planeHeight(o.points, ...point),
      maximumHeight: Math.max(...o.points.map((p) => Math.max(p.z_top, p.z_bottom))),
    })),
    layer === 0,
  );
};
const localEndpoint = (
  part: Level3DObject,
  point: Point,
  sector: number,
  layer: number,
  projectionPoint = point,
) => {
  const z = heightAt(sector, layer, point, projectionPoint);
  return localize(part, [point[0], point[1] + z, z]);
};
const movementTransitionRecovery: {
  patch: number;
  sector: number;
  layer: number;
  pair: number;
  asset: string;
  transition: string;
}[] = [];
for (const area of movementStateInventory)
  for (const change of area.transitions) {
    try {
      if (change.patches.length !== 1)
        throw new Error("Changing contours need one explicit patch owner");
      const source = proto.patches[change.patches[0]!]!;
      const refs = [...source.old_sight_obstacles, ...source.new_sight_obstacles];
      const owners = refs.map((ref) => {
        const matches = locals.get(ref) ?? [];
        if (matches.length !== 1) throw new Error(`Missing or ambiguous sight owner ${ref}`);
        return matches[0]!;
      });
      const declared = (ownership?.movement_transitions ?? []).filter(
        (entry) => entry.patch === change.patches[0],
      );
      if (declared.length > 1) throw new Error("Ambiguous explicit movement-transition ownership");
      if (declared[0]) {
        const { owner: asset, node } = declared[0];
        const parts = document.objects.filter((part) => part.node === `asset:${asset}:${node}`);
        if (parts.length !== 1 || !descriptors.get(asset)?.parts.some((part) => part.node === node))
          throw new Error("Explicit movement owner needs one pinned asset frame");
        owners.unshift({ asset, node, part: parts[0]! });
      }
      if (!owners.length)
        throw new Error("No sight ownership; explicit asset authoring is required");
      const owner = owners[0]!;
      if (owners.some((entry) => entry.asset !== owner.asset))
        throw new Error("Changing sight geometry spans assets; author independent local states");
      const p = packet(owner.asset);
      const descriptor = descriptors.get(owner.asset)!;
      const localRef = (index: number) => {
        const entry = locals.get(index)![0]!;
        return entry.collisionId ?? entry.node;
      };
      const initialSight = source.old_sight_obstacles.map(localRef);
      const appliedSight = source.new_sight_obstacles.map(localRef);
      const controlled = new Set([...initialSight, ...appliedSight]);
      const definition = recoverMovementTransition({
        id: `movement-change-${change.patches[0]}`,
        node: owner.node,
        patch: source,
        initial: change.initial,
        applied: change.applied,
        initialSight,
        appliedSight,
        receivers: proto.sight_obstacles.filter(
          (obstacle) =>
            Array.isArray(obstacle.projection_area) &&
            obstacle.projection_area[0] === area.sector &&
            obstacle.projection_area[1] === area.layer,
        ),
        groundLayer: area.layer === 0,
        waypointHeight: heightAt(source.sector, source.layer, source.waypoint),
        localize: (point) => localize(owner.part, point),
      });
      // Keep permanent solids and their clearances, excluding both changing endpoints.
      // Explicit stable contours already replace part-derived movement collision.
      if (p.movementBlockers === undefined) {
        const solids = p.movementSolids ?? [
          ...descriptor.parts
            .filter((part) => part.obstacle_local_game?.solid)
            .map((part) => part.node),
          ...(p.volumes ?? []).filter((volume) => volume.shape.solid).map((volume) => volume.id),
        ];
        p.movementSolids = solids.filter((ref) => !controlled.has(ref));
      }
      (p.movementTransitions ??= []).push(definition);
      p.issues.push(
        "Movement/sight states recovered; visual states and effects still need separate authoring",
      );
      movementTransitionRecovery.push({
        patch: change.patches[0]!,
        sector: area.sector,
        layer: area.layer,
        pair: change.pair,
        asset: owner.asset,
        transition: definition.id,
      });
    } catch (error) {
      unresolved.push({
        kind: "movement-states",
        sector: area.sector,
        layer: area.layer,
        pair: change.pair,
        reason: String(error),
      });
    }
  }
for (const [index, lift] of proto.lifts.entries()) {
  const supports = proto.sight_obstacles.flatMap((obstacle, support) =>
    Array.isArray(obstacle.projection_area) &&
    obstacle.projection_area[0] === lift.motion_area_index
      ? [{ obstacle, owners: locals.get(support) ?? [] }]
      : [],
  );
  if (!supports.length || supports.some((s) => s.owners.length !== 1)) {
    unresolved.push({
      kind: "lift-owner",
      lift: index,
      candidates: supports.flatMap((s) => s.owners.map((o) => o.asset)),
    });
    continue;
  }
  try {
    const joins = recoverLiftJoins(
      supports.map((s) => s.obstacle.points.map((p): Vec3 => [p.x, p.y, p.z_top])),
    );
    const endpointOwners = (lift.doors as SourceDoor[]).map((door) => {
      const matches = supports
        .map((s, i) => ({
          i,
          distance: distanceToPolygon(
            door.point_in,
            s.obstacle.points.map((p): Point => [p.x, p.y - p.z_top]),
          ),
        }))
        .filter((p) => p.distance === 0);
      if (matches.length !== 1)
        throw new Error("Lift endpoint does not have one supporting segment");
      return matches[0]!.i;
    });
    for (const [supportIndex, support] of supports.entries()) {
      const owner = support.owners[0]!;
      const doors = (lift.doors as SourceDoor[]).flatMap((door, i) =>
        endpointOwners[i] !== supportIndex
          ? []
          : [
              {
                id: `${owner.node}-endpoint-${i}`,
                node: owner.node,
                polygon: door.door_sector.points.map((point) => {
                  const z = heightAt(door.sector_out, door.layer_out, door.point_out);
                  const local = localize(owner.part, [point[0], point[1] + z, z]);
                  return [local[0], local[1]] as Point;
                }),
                inside: localEndpoint(owner.part, door.point_in, door.sector_in, door.layer_in),
                outside: localEndpoint(owner.part, door.point_out, door.sector_out, door.layer_out),
                // A transition midpoint can sit just outside its projection polygon.
                // Keep the plane selected by the actual inside endpoint.
                middle: localEndpoint(
                  owner.part,
                  door.point_mid,
                  door.sector_in,
                  door.layer_in,
                  door.point_in,
                ),
                type: door.door_type,
                locked: door.locked_pc,
                unlockable: door.unlockable,
                active: door.active,
                lockedVillains: door.locked_npc_villain,
                lockedCivilians: door.locked_npc_civilian,
                afterTransition: {
                  player: door.locked_pc_after_patch,
                  unlockable: door.unlockable_after_patch,
                  villains: door.locked_npc_villain_after_patch,
                  civilians: door.locked_npc_civilian_after_patch,
                },
              },
            ],
      );
      packet(owner.asset).connections.push({
        id: `${owner.node}-lift`,
        node: owner.node,
        kind: "lift",
        type: lift.lift_type,
        direction: (() => {
          const angle = (lift.direction * Math.PI) / 8;
          const origin = localize(owner.part, [0, 0, 0]);
          const tip = localize(owner.part, [Math.sin(angle), -Math.cos(angle), 0]);
          return [tip[0] - origin[0], tip[1] - origin[1]] as Point;
        })(),
        ...(joins[supportIndex]!.length
          ? { joins: joins[supportIndex]!.map((p) => localize(owner.part, p)) }
          : {}),
        endpoints: doors,
      });
    }
  } catch (error) {
    unresolved.push({ kind: "lift-endpoint", lift: index, reason: String(error) });
  }
}
// Building ownership must be spatially unambiguous; do not guess from asset names.
type SourceDoor = {
  point_in: Point;
  point_out: Point;
  point_mid: Point;
  sector_in: number;
  sector_out: number;
  layer_in: number;
  layer_out: number;
  door_sector: { points: Point[] };
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
};
let recoveredBuildings = 0;
const doorStateOwnershipRecovery: {
  building: number;
  doors: number[];
  asset: string;
  connection: string;
}[] = [];
const recoveredDoors = new Map<
  number,
  { asset: string; id: string; node: string; part: Level3DObject }
>();
let doorOffset = 0;
for (const [index, entry] of proto.buildings.entries()) {
  const building = entry as {
    Building?: { doors: SourceDoor[] };
    StandaloneDoors?: { doors: SourceDoor[] };
  };
  const groups = recoveryDoorGroups(building);
  const doorIndices = new Map(
    groups.flatMap((group) => group.doors).map((door) => [door, doorOffset++] as const),
  );
  if (!groups.length) {
    recoveredBuildings++;
    continue;
  }
  if (groups.some((g) => !g.doors.length)) {
    unresolved.push({ kind: "building-empty", building: index });
    continue;
  }
  let recovered = 0;
  for (const connection of groups) {
    const { doors, sourceDoor } = connection;
    const isInterior = connection.kind === "building-interior";
    try {
      const candidates = new Map<
        string,
        { owner: { asset: string; node: string; part: Level3DObject }; distance: number }
      >();
      const first = doors[0]!,
        z = isInterior
          ? heightAt(first.sector_out, first.layer_out, first.point_out)
          : heightAt(first.sector_in, first.layer_in, first.point_in);
      const raisedCandidates: typeof candidates = new Map();
      for (const [obstacleIndex, owners] of locals) {
        if (owners.length !== 1) continue;
        const obstacle = proto.sight_obstacles[obstacleIndex]!;
        if (!obstacle.solid) continue;
        if (Math.min(...obstacle.points.map((p) => p.z_bottom)) > z + 24) continue;
        const distance = distanceToPolygon(
          [first.point_in[0], first.point_in[1] + z],
          obstacle.points.map((p) => [p.x, p.y]),
        );
        const owner = owners[0]!,
          previous = candidates.get(owner.asset);
        if (!previous || distance < previous.distance)
          candidates.set(owner.asset, { owner, distance });
        const footprints = doorOwnershipFootprint(obstacle, z);
        if (footprints.length) {
          const raisedDistance = Math.min(
            ...footprints.map((footprint) =>
              distanceToPolygon([first.point_in[0], first.point_in[1] + z], footprint),
            ),
          );
          const previousRaised = raisedCandidates.get(owner.asset);
          if (!previousRaised || raisedDistance < previousRaised.distance)
            raisedCandidates.set(owner.asset, { owner, distance: raisedDistance });
        }
      }
      const ranked = [...candidates.values()].sort((a, b) => a.distance - b.distance);
      const choose = (entries: typeof ranked) =>
        entries[0] &&
        entries[0].distance <= 24 &&
        (!entries[1] || entries[1].distance - entries[0].distance >= 8)
          ? entries[0].owner
          : undefined;
      const spatialOwner =
        choose(ranked) ??
        choose([...raisedCandidates.values()].sort((a, b) => a.distance - b.distance));
      const stateOwner = recoverDoorStateOwner(
        doors.map((door) => doorIndices.get(door)!),
        proto.patches,
        locals,
      );
      if (!stateOwner && !spatialOwner) {
        unresolved.push({
          kind: "building-owner",
          building: index,
          sourceDoor,
          candidates: ranked
            .slice(0, 4)
            .map((c) => ({ asset: c.owner.asset, distance: c.distance })),
        });
        continue;
      }
      const owner = stateOwner ?? spatialOwner!;
      if (!stateOwner && !choose(ranked))
        packet(owner.asset).issues.push(
          "Door ownership resolved from geometry above its landing; review the physical doorway before publication",
        );
      const endpoints = doors.map((door, i) => {
        const elevation = heightAt(door.sector_out, door.layer_out, door.point_out);
        const local = (point: Point) =>
          localize(owner.part, [point[0], point[1] + elevation, elevation]);
        return {
          id: `door-${i}`,
          node: owner.node,
          polygon: door.door_sector.points.map(local),
          outside: local(door.point_out),
          inside: isInterior
            ? local(door.point_in)
            : localEndpoint(owner.part, door.point_in, door.sector_in, door.layer_in),
          middle: local(door.point_mid),
          type: door.door_type,
          active: door.active,
          locks: {
            player: door.locked_pc,
            unlockable: door.unlockable,
            villains: door.locked_npc_villain,
            civilians: door.locked_npc_civilian,
          },
          afterTransition: {
            player: door.locked_pc_after_patch,
            unlockable: door.unlockable_after_patch,
            villains: door.locked_npc_villain_after_patch,
            civilians: door.locked_npc_civilian_after_patch,
          },
        };
      });
      const connectionId = `${isInterior ? "interior" : "passage"}-${packet(owner.asset).connections.length}`;
      packet(owner.asset).connections.push({
        id: connectionId,
        node: owner.node,
        kind: connection.kind,
        endpoints,
      });
      if (stateOwner) {
        doorStateOwnershipRecovery.push({
          building: index,
          doors: doors.map((door) => doorIndices.get(door)!),
          asset: owner.asset,
          connection: connectionId,
        });
        packet(owner.asset).issues.push(
          "Door ownership follows linked state geometry; review physical asset grouping before publication",
        );
      }
      doors.forEach((door, i) => {
        recoveredDoors.set(doorIndices.get(door)!, {
          asset: owner.asset,
          id: `${connectionId}/${endpoints[i]!.id}`,
          node: owner.node,
          part: owner.part,
        });
      });
      recovered++;
    } catch (error) {
      unresolved.push({
        kind: "building-endpoint",
        building: index,
        sourceDoor,
        reason: String(error),
      });
    }
  }
  if (recovered === groups.length) recoveredBuildings++;
}
const doorTransitionRecovery: { patch: number; asset: string; transition: string }[] = [];
for (const [index, source] of proto.patches.entries()) {
  if (!source.door_indices.length) continue;
  try {
    const transitions = movementTransitionRecovery.filter((entry) => entry.patch === index);
    const doorOwners = source.door_indices.map((door) => {
      const owner = recoveredDoors.get(door);
      if (!owner) throw new Error(`Missing door ownership ${door}`);
      return owner;
    });
    const owner = doorOwners[0]!;
    if (doorOwners.some((entry) => entry.asset !== owner.asset))
      throw new Error("Linked doors belong to different assets");
    if (!source.door_triggered && !source.triggers_door)
      throw new Error("Door binding has neither trigger nor rights-swap semantics");
    if (transitions.length > 1)
      throw new Error("Door binding needs one recovered asset-local transition");
    const recovered = transitions[0];
    if (recovered && recovered.asset !== owner.asset)
      throw new Error("Door and its transition belong to different assets");
    if (
      !recovered &&
      movementStateInventory.some((area) =>
        area.transitions.some((change) => change.patches.includes(index)),
      )
    )
      throw new Error("Door transition has unrecovered movement changes");
    const sightRef = (index: number) => {
      const candidates = locals.get(index) ?? [];
      if (candidates.length !== 1)
        throw new Error(`Door transition needs one sight owner for obstacle ${index}`);
      const sight = candidates[0]!;
      if (sight.asset !== owner.asset)
        throw new Error(`Door and sight obstacle ${index} belong to different assets`);
      return sight.collisionId ?? sight.node;
    };
    const initialSight = source.old_sight_obstacles.map(sightRef);
    const appliedSight = source.new_sight_obstacles.map(sightRef);
    const p = packet(owner.asset);
    const transition = recovered
      ? p.movementTransitions!.find((entry) => entry.id === recovered.transition)!
      : recoverMovementTransition({
          id: `door-change-${index}`,
          node: owner.node,
          patch: source,
          initial: [],
          applied: [],
          initialSight,
          appliedSight,
          receivers: [],
          groundLayer: source.layer === 0,
          waypointHeight: heightAt(source.sector, source.layer, source.waypoint),
          localize: (point) => localize(owner.part, point),
        });
    transition.doorLinks = {
      mode: source.door_triggered ? "trigger-transition" : "swap-rights",
      ids: doorOwners.map((entry) => entry.id),
    };
    if (
      !recovered &&
      (initialSight.length || appliedSight.length) &&
      p.movementBlockers === undefined
    ) {
      const descriptor = descriptors.get(owner.asset)!;
      const controlled = new Set([...initialSight, ...appliedSight]);
      const solids = p.movementSolids ?? [
        ...descriptor.parts
          .filter((part) => part.obstacle_local_game?.solid)
          .map((part) => part.node),
        ...(p.volumes ?? []).filter((volume) => volume.shape.solid).map((volume) => volume.id),
      ];
      p.movementSolids = solids.filter((ref) => !controlled.has(ref));
    }
    if (!recovered) (p.movementTransitions ??= []).push(transition);
    p.issues.push("Door bindings recovered; visual states and effects need separate authoring");
    doorTransitionRecovery.push({
      patch: index,
      asset: owner.asset,
      transition: transition.id,
    });
  } catch (error) {
    unresolved.push({ kind: "door-transition", patch: index, reason: String(error) });
  }
}
// Ground regions belong to the terrain asset. Obstacle-only regions must have
// explicit local owners; unresolved projection links stay in the recovery report.
const groundMaterialOwners = [...descriptors.values()].filter(
  (d) => d.editor_usage === "map-background",
);
if (groundMaterialOwners.length === 1) {
  packet(groundMaterialOwners[0]!.id).environment = {
    forest: proto.misc.forest_level,
    defaultMaterial: proto.misc.default_material,
  };
} else
  unresolved.push({
    kind: "map-environment-owner",
    candidates: groundMaterialOwners.map((d) => d.id),
  });
const recoveredMaterials = new Set<number>();
for (const index of proto.sight_material_indices) {
  const region = proto.material_sectors[index];
  if (!region || groundMaterialOwners.length !== 1) {
    unresolved.push({
      kind: "ground-material-owner",
      index,
      candidates: groundMaterialOwners.map((d) => d.id),
    });
    continue;
  }
  const p = packet(groundMaterialOwners[0]!.id);
  (p.materials ??= []).push({
    id: `ground-material-${p.materials?.length ?? 0}`,
    node: "$root",
    material: region.material,
    ground: true,
    obstacles: [],
    polygon: region.polygon.points.map(([x, y]) => [x, y, 0]),
  });
  recoveredMaterials.add(index);
}
for (const [index, obstacle] of proto.sight_obstacles.entries()) {
  if (!obstacle.material_indices.length) continue;
  const owners = locals.get(index) ?? [];
  if (!owners.length || obstacle.projection_area !== null) {
    unresolved.push({
      kind: "obstacle-material-owner",
      obstacle: index,
      reason:
        obstacle.projection_area !== null
          ? "Projection-surface material links still need recovery"
          : "No asset-local owner",
    });
    continue;
  }
  for (const material of obstacle.material_indices) {
    const region = proto.material_sectors[material];
    if (!region) throw new Error(`Missing material region ${material}`);
    for (const owner of owners) {
      const p = packet(owner.asset);
      (p.materials ??= []).push({
        id: `obstacle-material-${p.materials?.length ?? 0}`,
        node: owner.node,
        material: region.material,
        ground: false,
        obstacles: [owner.collisionId ?? owner.node],
        polygon: region.polygon.points.map(([x, y]) => localize(owner.part, [x, y, 0])),
      });
    }
    recoveredMaterials.add(material);
  }
}
let recoveredSounds = 0;
for (const [index, sound] of proto.sound_sources.entries()) {
  if (sound.global && groundMaterialOwners.length === 1) {
    const p = packet(groundMaterialOwners[0]!.id);
    (p.sounds ??= []).push(recoverSoundSource(sound, `ambient-sound-${index}`, "$root", (p) => p));
    recoveredSounds++;
    continue;
  }
  const owners = [...locals.values()].flat().filter((owner) => {
    const shape = owner.sourceShape ?? transformedObstacle(document, owner.part);
    return (
      sound.polyline &&
      containsSoundPolyline(
        sound.polyline,
        shape.points.map((p) => [p.x, p.y]),
      )
    );
  });
  if (owners.length !== 1) {
    unresolved.push({
      kind: "sound-owner",
      source: index,
      sample: sound.id,
      candidates: owners.map(({ asset, node }) => ({ asset, node })),
      reason: "Local emitter needs explicit asset ownership; no terrain fallback",
    });
    continue;
  }
  const owner = owners[0]!;
  const p = packet(owner.asset);
  (p.sounds ??= []).push(
    recoverSoundSource(sound, `ambient-sound-${index}`, owner.node, (point) =>
      localize(owner.part, point),
    ),
  );
  p.issues.push("Review environmental sound ownership inferred from unique geometric containment");
  recoveredSounds++;
}
let recoveredLights = 0;
for (const [index, light] of proto.light_sectors.entries()) {
  try {
    const plane = recoverLightPlane(light, proto.sight_obstacles);
    const world = recoverLightRegion(light, `light-${index}`, "$root", plane, (p) => p);
    const contour = world.polygon.map(([x, y]): Point => [x, y]);
    const owners = [...locals.values()].flat().filter((owner) =>
      containsSoundPolyline(
        [...contour, contour[0]!],
        (owner.sourceShape ?? transformedObstacle(document, owner.part)).points.map((p): Point => [
          p.x,
          p.y,
        ]),
      ),
    );
    if (owners.length !== 1) {
      unresolved.push({
        kind: "light-owner",
        source: index,
        candidates: owners.map(({ asset, node }) => ({ asset, node })),
        reason: "Light region needs explicit asset ownership; no terrain fallback",
      });
      continue;
    }
    const owner = owners[0]!,
      p = packet(owner.asset);
    (p.lights ??= []).push(
      recoverLightRegion(light, `light-${index}`, owner.node, plane, (point) =>
        localize(owner.part, point),
      ),
    );
    p.issues.push("Review light-region ownership inferred from unique geometric containment");
    recoveredLights++;
  } catch (error) {
    unresolved.push({ kind: "light-geometry", source: index, error: String(error) });
  }
}
let recoveredJumps = 0;
type JumpOwner = { asset: string; node: string; part?: Level3DObject };
const jumpPoint = (owner: JumpOwner, p: Vec3) => (owner.part ? localize(owner.part, p) : p);
for (const [index, pair] of proto.jump_line_pairs.entries()) {
  try {
    const sideCandidates = [pair.line1, pair.line2].map((line, side): JumpOwner[] => {
      const home = proto.jump_zones[(side === 0 ? pair.line2 : pair.line1).jump_zone_index];
      if (!home) throw new Error("Jump pair references a missing receiving zone");
      const supports = proto.sight_obstacles.flatMap((o, obstacleIndex) =>
        Array.isArray(o.projection_area) &&
        o.projection_area[0] === home.sector &&
        o.projection_area[1] === home.layer
          ? (locals.get(obstacleIndex) ?? [])
          : [],
      );
      const sideOwners = jumpEdgeOwners(
        line,
        supports,
        (owner) => owner.sourceShape ?? transformedObstacle(document, owner.part),
      );
      if (!sideOwners.length && home.layer !== 0)
        throw new Error(`Jump side ${side} has no owned elevated receiving surface`);
      return sideOwners;
    });
    if (sideCandidates.every((side) => !side.length) && groundMaterialOwners.length === 1) {
      const terrain = packet(groundMaterialOwners[0]!.id);
      if (
        terrainOwnsJump(
          pair,
          proto.jump_zones,
          groundAreaSectors,
          terrain.surfaces,
          transferredGroundExclusions,
        )
      ) {
        const owner = { asset: terrain.asset, node: "$root" };
        sideCandidates[0]!.push(owner);
        sideCandidates[1]!.push(owner);
      }
    }
    const candidates = sideCandidates.flat();
    const assets = new Set(candidates.map((o) => o.asset));
    if (
      assets.size === 2 &&
      sideCandidates.every((c) => new Set(c.map((o) => o.asset)).size === 1)
    ) {
      const recovered = ([0, 1] as const).map((side) => {
        const owner =
          [...locals.values()].flat().find((o) => o.asset === sideCandidates[side]![0]!.asset) ??
          sideCandidates[side]![0]!;
        return {
          owner,
          ...recoverJumpSegment(
            side,
            proto,
            index,
            owner.node,
            (point) => jumpPoint(owner, point),
            (zone, point) => heightAt(zone.sector, zone.layer, point),
          ),
        };
      });
      for (const { owner, zone } of recovered) {
        const previous = packet(owner.asset).jumpZones?.find((z) => z.id === zone.id);
        if (previous && JSON.stringify(previous) !== JSON.stringify(zone))
          throw new Error(`Shared jump zone ${zone.id} needs consistent owner and anchor`);
      }
      for (const { owner, zone, segment } of recovered) {
        const p = packet(owner.asset);
        if (!p.jumpZones?.some((z) => z.id === zone.id)) (p.jumpZones ??= []).push(zone);
        (p.jumpSegments ??= []).push(segment);
        p.issues.push("Review cross-asset jump sockets and landing ownership before publication");
      }
      recoveredJumps++;
      continue;
    }
    if (assets.size !== 1) {
      unresolved.push({
        kind: "jump-owner",
        source: index,
        candidates: [...assets],
        reason:
          "Each jump side needs one explicit asset owner; ambiguous ownership must be authored",
      });
      continue;
    }
    const owner =
        [...locals.values()].flat().find((o) => o.asset === candidates[0]!.asset) ?? candidates[0]!,
      p = packet(owner.asset);
    const recovered = recoverJumpGeometry(
      proto,
      index,
      owner.node,
      (point) => jumpPoint(owner, point),
      (zone, point) => heightAt(zone.sector, zone.layer, point),
    );
    for (const zone of recovered.zones) {
      const previous = p.jumpZones?.find((z) => z.id === zone.id);
      if (previous && JSON.stringify(previous) !== JSON.stringify(zone))
        throw new Error(`Shared jump zone ${zone.id} needs consistent owner and anchor`);
    }
    for (const zone of recovered.zones)
      if (!p.jumpZones?.some((z) => z.id === zone.id)) (p.jumpZones ??= []).push(zone);
    (p.jumpPairs ??= []).push(recovered.pair);
    p.issues.push(
      "Review jump ownership inferred from projection surfaces, landing anchors and click-region height",
    );
    recoveredJumps++;
  } catch (error) {
    unresolved.push({ kind: "jump-geometry", source: index, error: String(error) });
  }
}
const pending = {
  doorTransitionBindings:
    proto.patches.filter((patch) => patch.door_indices.length > 0).length -
    doorTransitionRecovery.length,
  movementTransitions:
    movementStateInventory.reduce((sum, area) => sum + area.transitions.length, 0) -
    movementTransitionRecovery.length,
  buildingEntries: proto.buildings.length - recoveredBuildings,
  maskRecords: proto.masks.length,
  patches: proto.patches.length,
  jumpPairs: proto.jump_line_pairs.length - recoveredJumps,
  materialRegions: proto.material_sectors.length - recoveredMaterials.size,
  shadowRegions: proto.light_sectors.length - recoveredLights,
  soundSources: proto.sound_sources.length - recoveredSounds,
};
await fs.mkdir(values.out, { recursive: true });
const definitionValidation: { asset: string; valid: boolean; error?: string }[] = [];
for (const [asset, p] of packets) {
  try {
    const descriptor = descriptors.get(asset);
    if (!descriptor) throw new Error(`Missing pinned descriptor ${asset}`);
    p.gameplayCandidate = recoveredGameplayDefinition(p, descriptor);
    definitionValidation.push({ asset, valid: true });
  } catch (error) {
    definitionValidation.push({ asset, valid: false, error: String(error) });
  }
  p.issues = [...new Set(p.issues)];
  await fs.writeFile(
    path.join(values.out, `${asset}.gameplay-authoring.json`),
    JSON.stringify(p, null, 2) + "\n",
  );
}
// Probe the assembled scene using only the candidate asset definitions. Keep
// this diagnostic separate from publication and from recovery coverage.
const candidates = new Map<string, GameplayAssetDescriptor>(descriptors);
for (const [id, descriptor] of candidates) {
  const gameplay = packets.get(id)?.gameplayCandidate;
  if (gameplay) candidates.set(id, { ...descriptor, gameplay });
}
const diagnostics = diagnoseGameplayCandidates(document, candidates, {
  omittedMovementTransitions: pending.movementTransitions,
});
const report = {
  status: "incomplete-authoring-recovery",
  assets: packets.size,
  files: [...packets.keys()].sort().map((asset) => `${asset}.gameplay-authoring.json`),
  surfaces: [...packets.values()].reduce((sum, p) => sum + p.surfaces.length, 0),
  connections: [...packets.values()].reduce((sum, p) => sum + p.connections.length, 0),
  movementBlockers: [...packets.values()].reduce(
    (sum, p) => sum + (p.movementBlockers?.length ?? 0),
    0,
  ),
  definitionValidation,
  movementStateInventory,
  movementTransitionRecovery,
  doorTransitionRecovery,
  doorStateOwnershipRecovery,
  candidateCompilation: diagnostics.compilation,
  staticGeometryDiagnostic: diagnostics.staticGeometry,
  coverage,
  unresolved,
  pending,
};
await fs.writeFile(
  path.join(values.out, "recovery-report.json"),
  JSON.stringify(report, null, 2) + "\n",
);
console.log(
  JSON.stringify({
    assets: report.assets,
    surfaces: report.surfaces,
    connections: report.connections,
    unresolved: unresolved.length,
    pending,
  }),
);
