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
import { recoverJumpGeometry } from "./recover-jump-geometry.ts";
import { recoveryDoorGroups } from "./recovery-door-groups.ts";
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
const locals = new Map<number, { asset: string; node: string; part: Level3DObject }[]>();
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
const coverage: unknown[] = [];
const groundAreas: Parameters<typeof recoverGroundGameplay>[0] = [];
const clearanceSources: { regions: MultiPolygon; plane: HeightPlane }[] = [];
const groundProjectionOwners: {
  asset: string;
  node: string;
  part: Level3DObject;
  footprint: Point[];
}[] = [];
let sector = 0;
for (const [layer, areas] of proto.motion_data.layers.entries())
  for (const motion of areas) {
    const identity = sector;
    sector += 1 + motion.obstacles.length;
    if (motion.state_id !== 0 || motion.obstacles.some((o) => o.state_id !== 0))
      unresolved.push({
        kind: "movement-states",
        sector: identity,
        layer,
        reason:
          "State-dependent movement exclusions require asset state ownership; static drafts are incomplete",
      });
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
          regions: partition.surfaces[supportIndex]!,
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
        );
        owned = split.owned;
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
            id: `${owner.node}-walk-${regionIndex}`,
            node: owner.node,
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
    const terrain = packet(grounds[0]!.id);
    for (const [index, region] of ground.terrain.entries())
      terrain.surfaces.push({
        id: `ground-${index}`,
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
      if (!definition?.obstacle_local_game?.solid) continue;
      const solid = transformedObstacle(document, {
        ...owner.part,
        obstacle: definition.obstacle_local_game,
      });
      let regions: MultiPolygon;
      try {
        regions = recoverMovementClearance(source.regions, source.plane, solid);
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
for (const [index, lift] of proto.lifts.entries()) {
  const support = proto.sight_obstacles.findIndex(
    (o) => Array.isArray(o.projection_area) && o.projection_area[0] === lift.motion_area_index,
  );
  const owners = locals.get(support) ?? [];
  if (owners.length !== 1) {
    unresolved.push({ kind: "lift-owner", lift: index, candidates: owners.map((o) => o.asset) });
    continue;
  }
  const owner = owners[0]!;
  try {
    const doors = (lift.doors as SourceDoor[]).map((door, i) => ({
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
    }));
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
      endpoints: doors,
    });
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
for (const [index, entry] of proto.buildings.entries()) {
  const building = entry as {
    Building?: { doors: SourceDoor[] };
    StandaloneDoors?: { doors: SourceDoor[] };
  };
  const groups = recoveryDoorGroups(building);
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
      }
      const ranked = [...candidates.values()].sort((a, b) => a.distance - b.distance);
      if (
        !ranked[0] ||
        ranked[0].distance > 24 ||
        (ranked[1] && ranked[1].distance - ranked[0].distance < 8)
      ) {
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
      const owner = ranked[0].owner;
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
      packet(owner.asset).connections.push({
        id: `${isInterior ? "interior" : "passage"}-${packet(owner.asset).connections.length}`,
        node: owner.node,
        kind: connection.kind,
        endpoints,
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
        obstacles: [owner.node],
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
    const shape = transformedObstacle(document, owner.part);
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
        transformedObstacle(document, owner.part).points.map((p): Point => [p.x, p.y]),
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
for (const [index, pair] of proto.jump_line_pairs.entries()) {
  try {
    const candidates = [pair.line1, pair.line2].flatMap((line, side) => {
      const home = proto.jump_zones[(side === 0 ? pair.line2 : pair.line1).jump_zone_index];
      if (!home) throw new Error("Jump pair references a missing receiving zone");
      return proto.sight_obstacles.flatMap((o, obstacleIndex) =>
        Array.isArray(o.projection_area) &&
        o.projection_area[0] === home.sector &&
        o.projection_area[1] === home.layer &&
        containsSoundPolyline(
          [line.point_a.slice(0, 2) as Point, line.point_b.slice(0, 2) as Point],
          o.points.map((p): Point => [p.x, p.y - p.z_top]),
        )
          ? (locals.get(obstacleIndex) ?? [])
          : [],
      );
    });
    const assets = new Set(candidates.map((o) => o.asset));
    if (assets.size !== 1) {
      unresolved.push({
        kind: "jump-owner",
        source: index,
        candidates: [...assets],
        reason:
          "Jump pair requires one explicit owning asset; cross-asset ownership must be authored",
      });
      continue;
    }
    const owner = [...locals.values()].flat().find((o) => o.asset === candidates[0]!.asset)!,
      p = packet(owner.asset);
    const recovered = recoverJumpGeometry(
      proto,
      index,
      owner.node,
      (point) => localize(owner.part, point),
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
const diagnostics = diagnoseGameplayCandidates(document, candidates);
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
