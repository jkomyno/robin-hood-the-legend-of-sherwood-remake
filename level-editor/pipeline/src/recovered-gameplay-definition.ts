import type { Point, Vec3, ProjectionAssetDescriptor } from "@rle/shared";
import {
  validateAssetGameplay,
  type AssetGameplay,
  type AssetDoor,
  type AssetWalkableSurface,
} from "../../shared/src/asset-gameplay.ts";
import { heightPlane, planeHeight } from "../../shared/src/gameplay-plane.ts";

export interface RecoveredSurface {
  id: string;
  node: string;
  vertices: Vec3[];
  holes: Vec3[][];
  kind?: "walkable" | "lift";
}
type Locks = { player: boolean; unlockable: boolean; villains: boolean; civilians: boolean };
export interface RecoveredDoor {
  id: string;
  node: string;
  polygon: (Point | Vec3)[];
  inside: Vec3;
  outside: Vec3;
  middle: Vec3;
  type: number;
  active: boolean;
  locked?: boolean;
  unlockable?: boolean;
  lockedVillains?: boolean;
  lockedCivilians?: boolean;
  locks?: Locks;
  afterTransition?: Locks;
}
export interface RecoveredConnection {
  id: string;
  node: string;
  kind: "lift" | "building-interior" | "passage";
  type?: number;
  direction?: Point;
  endpoints: RecoveredDoor[];
}
export interface RecoveredGameplayPacket {
  asset: string;
  surfaces: RecoveredSurface[];
  /** Omitted means derive collision from parts; an empty list explicitly disables that derivation. */
  movementBlockers?: RecoveredSurface[];
  movementClearances?: RecoveredSurface[];
  materials?: AssetGameplay["materials"];
  environment?: AssetGameplay["environment"];
  connections: RecoveredConnection[];
}

/** Seed geometry that is already authored in the asset, before recovering additional gameplay. */
export function descriptorGameplayPacket(
  descriptor: ProjectionAssetDescriptor,
): RecoveredGameplayPacket {
  if (descriptor.editor_usage === "map-background")
    throw new Error(`${descriptor.id}: terrain needs authored movement boundaries`);
  if (!descriptor.parts.length)
    throw new Error(`${descriptor.id}: asset has no geometry definitions`);
  const surfaces: RecoveredSurface[] = [];
  for (const part of descriptor.parts) {
    const node = part.node;
    if (part.scenery) continue;
    if (!part.obstacle_local_game)
      throw new Error(`${descriptor.id}/${node}: missing local collision shape`);
    // Mission-authored surfaces have no extracted obstacle identity. Their
    // local geometry is authoritative; map-wide projection indices are discarded.
    if (part.mission_profile && part.obstacle_local_game.projection_area !== null)
      surfaces.push({
        id: `${part.node}-surface`,
        node: part.node,
        kind: "walkable",
        vertices: part.obstacle_local_game.points.map((p) => [p.x, p.y, p.z_top]),
        holes: [],
      });
  }
  return { asset: descriptor.id, surfaces, connections: [] };
}

/** Convert authoring drafts to the compiler schema. This does not certify recovery completeness. */
export function recoveredGameplayDefinition(
  packet: RecoveredGameplayPacket,
  descriptor: ProjectionAssetDescriptor,
): AssetGameplay {
  if (packet.asset !== descriptor.id)
    throw new Error("Recovery packet asset does not match descriptor");
  const surface = (draft: RecoveredSurface): AssetWalkableSurface => {
    const plane = heightPlane(draft.vertices);
    for (const hole of draft.holes)
      for (const [x, y, z] of hole)
        if (Math.abs(planeHeight(plane, [x, y]) - z) > 1e-4)
          throw new Error(`${draft.id}: hole is not on its surface plane`);
    return {
      id: draft.id,
      node: draft.node,
      polygon: draft.vertices.map(([x, y]) => [x, y]),
      height: draft.vertices.map((p) => p[2]),
      holes: draft.holes.map((hole) => hole.map(([x, y]) => [x, y])),
    };
  };
  const door = (connection: RecoveredConnection, d: RecoveredDoor): AssetDoor => {
    // Click polygons are planar at the outside endpoint's elevation. Do not
    // silently flatten a recovered polygon from another elevation.
    if (d.polygon.some((p) => p.length === 3 && Math.abs(p[2] - d.outside[2]) > 1e-4))
      throw new Error(
        `${connection.id}/${d.id}: door polygon elevation does not match its outside endpoint`,
      );
    return {
      id: `${connection.id}/${d.id}`,
      node: d.node,
      polygon: d.polygon.map(([x, y]) => [x, y]),
      inside: d.inside,
      outside: d.outside,
      middle: d.middle,
      type: d.type,
      active: d.active,
      locked: d.locks?.player ?? d.locked!,
      unlockable: d.locks?.unlockable ?? d.unlockable!,
      lockedVillains: d.locks?.villains ?? d.lockedVillains,
      lockedCivilians: d.locks?.civilians ?? d.lockedCivilians,
      ...(d.afterTransition
        ? {
            afterTransition: {
              locked: d.afterTransition.player,
              unlockable: d.afterTransition.unlockable,
              lockedVillains: d.afterTransition.villains,
              lockedCivilians: d.afterTransition.civilians,
            },
          }
        : {}),
    };
  };
  const gameplay: AssetGameplay = {
    version: 1,
    collision: descriptor.parts.some((p) => p.obstacle_local_game) ? "parts" : "none",
    surfaces: packet.surfaces.map(surface),
    ...(packet.environment ? { environment: { ...packet.environment } } : {}),
    ...(packet.materials ? { materials: structuredClone(packet.materials) } : {}),
    ...(packet.movementClearances
      ? { movementClearances: packet.movementClearances.map(surface) }
      : {}),
    ...(packet.movementBlockers !== undefined
      ? { movementBlockers: packet.movementBlockers.map(surface) }
      : {}),
    doors: [],
    lifts: [],
    interiors: [],
  };
  const assignedLifts = new Set<string>();
  for (const connection of packet.connections) {
    const doors = connection.endpoints.map((d) => door(connection, d));
    if (connection.kind === "passage") gameplay.doors.push(...doors);
    else if (connection.kind === "building-interior")
      gameplay.interiors!.push({ id: connection.id, node: connection.node, doors });
    else {
      const candidates = packet.surfaces.filter(
        (s) => s.node === connection.node && s.kind === "lift",
      );
      if (candidates.length !== 1)
        throw new Error(
          `${connection.id}: lift needs one owned traversal surface, found ${candidates.length}`,
        );
      assignedLifts.add(candidates[0]!.id);
      gameplay.lifts!.push({
        id: connection.id,
        node: connection.node,
        surface: candidates[0]!.id,
        type: connection.type as 1 | 2 | 3,
        direction: connection.direction!,
        doors,
      });
    }
  }
  for (const s of packet.surfaces)
    if (s.kind === "lift" && !assignedLifts.has(s.id))
      throw new Error(`${s.id}: recovered traversal surface has no connection definition`);
  validateAssetGameplay(gameplay, descriptor);
  return gameplay;
}
