/** One-time authoring migration. Never imported by the editor's map compiler. */
import fs from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import polygonClipping, { type Polygon } from "polygon-clipping";
import {
  gameToScene,
  sceneToGame,
  partMatrix,
  type Level3DObject,
  type Vec3,
  type Point,
  type ProtoLevel,
} from "@rle/shared";
import { readStoredMap } from "./stored-map.ts";

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
const proto: ProtoLevel = JSON.parse(await fs.readFile(values.source, "utf8"));
const locals = new Map<number, { asset: string; node: string; part: Level3DObject }[]>();
for (const part of document.objects) {
  const match = /^asset:([^:]+):(.+)$/.exec(part.node);
  if (!match || part.source.obstacle === undefined) continue;
  const list = locals.get(part.source.obstacle) ?? [];
  if (!list.some((item) => item.asset === match[1]))
    list.push({ asset: match[1]!, node: match[2]!, part });
  locals.set(part.source.obstacle, list);
}
const packets = new Map<
  string,
  {
    version: 1;
    status: "needs-review";
    asset: string;
    surfaces: unknown[];
    connections: unknown[];
    issues: string[];
  }
>();
const packet = (asset: string) => {
  let p = packets.get(asset);
  if (!p) {
    p = { version: 1, status: "needs-review", asset, surfaces: [], connections: [], issues: [] };
    packets.set(asset, p);
  }
  return p;
};
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
const area = (points: Point[]) =>
  Math.abs(
    points.reduce((s, a, i) => {
      const b = points[(i + 1) % points.length]!;
      return s + a[0] * b[1] - b[0] * a[1];
    }, 0),
  ) / 2;
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
let sector = 0;
for (const [layer, areas] of proto.motion_data.layers.entries())
  for (const motion of areas) {
    const identity = sector;
    sector += 1 + motion.obstacles.length;
    const supports = proto.sight_obstacles.flatMap((obstacle, index) =>
      Array.isArray(obstacle.projection_area) &&
      obstacle.projection_area[0] === identity &&
      obstacle.projection_area[1] === layer
        ? [{ obstacle, index }]
        : [],
    );
    if (!supports.length) {
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
    for (const { obstacle, index } of supports) {
      const owners = locals.get(index) ?? [];
      if (owners.length !== 1) {
        unresolved.push({
          kind: "surface-owner",
          sector: identity,
          layer,
          obstacle: index,
          candidates: owners.map((o) => o.asset),
        });
        continue;
      }
      const owner = owners[0]!;
      const regions = polygonClipping.intersection(
        close(motion.polygon.points),
        close(obstacle.points.map((p) => [p.x, p.y - p.z_top])),
      );
      for (const [regionIndex, region] of regions.entries()) {
        const points = region[0]!.slice(0, -1).map(([x, y]) => [x, y] as Point);
        recoveredArea += area(points);
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
            "Lift surfaces require their paired traversal endpoints and authored movement type",
          );
      }
    }
    coverage.push({
      sector: identity,
      layer,
      sourceArea: area(motion.polygon.points),
      recoveredArea,
    });
  }
// Recover lifts only where their surface has a unique owner. Neighbour endpoints
// remain geometric queries; no source sector or layer indices enter asset packets.
const heightAt = (sector: number, layer: number, point: Point) => {
  const support = proto.sight_obstacles.find(
    (o) =>
      Array.isArray(o.projection_area) &&
      o.projection_area[0] === sector &&
      o.projection_area[1] === layer,
  );
  if (support) return planeHeight(support.points, ...point);
  if (layer === 0) return 0;
  throw new Error(`Cannot recover endpoint elevation in sector ${sector}, layer ${layer}`);
};
const localEndpoint = (part: Level3DObject, point: Point, sector: number, layer: number) => {
  const z = heightAt(sector, layer, point);
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
    const doors = (
      lift.doors as {
        point_in: Point;
        point_out: Point;
        point_mid: Point;
        sector_in: number;
        sector_out: number;
        layer_in: number;
        layer_out: number;
        door_type: number;
        locked_pc: boolean;
        unlockable: boolean;
        active: boolean;
      }[]
    ).map((door, i) => ({
      id: `${owner.node}-endpoint-${i}`,
      inside: localEndpoint(owner.part, door.point_in, door.sector_in, door.layer_in),
      outside: localEndpoint(owner.part, door.point_out, door.sector_out, door.layer_out),
      middle: localEndpoint(owner.part, door.point_mid, door.sector_in, door.layer_in),
      type: door.door_type,
      locked: door.locked_pc,
      unlockable: door.unlockable,
      active: door.active,
    }));
    packet(owner.asset).connections.push({
      id: `${owner.node}-lift`,
      node: owner.node,
      kind: "lift",
      type: lift.lift_type,
      direction: lift.direction,
      endpoints: doors,
    });
  } catch (error) {
    unresolved.push({ kind: "lift-endpoint", lift: index, reason: String(error) });
  }
}
// Building ownership must be spatially unambiguous; do not guess from asset names.
const distanceToPolygon = (point: Point, points: Point[]) => {
  let inside = false,
    distance = Infinity;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const a = points[i]!,
      b = points[j]!,
      dx = b[0] - a[0],
      dy = b[1] - a[1];
    if (
      a[1] > point[1] !== b[1] > point[1] &&
      point[0] < ((b[0] - a[0]) * (point[1] - a[1])) / (b[1] - a[1]) + a[0]
    )
      inside = !inside;
    const t = Math.max(
      0,
      Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy || 1)),
    );
    distance = Math.min(distance, Math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy));
  }
  return inside ? 0 : distance;
};
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
  const doors = building.Building?.doors ?? building.StandaloneDoors?.doors;
  if (!doors?.length) {
    unresolved.push({ kind: "building-empty", building: index });
    continue;
  }
  try {
    const candidates = new Map<
      string,
      { owner: { asset: string; node: string; part: Level3DObject }; distance: number }
    >();
    const first = doors[0]!,
      z = heightAt(first.sector_out, first.layer_out, first.point_out);
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
        candidates: ranked.slice(0, 4).map((c) => ({ asset: c.owner.asset, distance: c.distance })),
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
        inside: building.Building
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
      id: `interior-${packet(owner.asset).connections.length}`,
      node: owner.node,
      kind: building.Building ? "building-interior" : "passage",
      endpoints,
    });
    recoveredBuildings++;
  } catch (error) {
    unresolved.push({ kind: "building-endpoint", building: index, reason: String(error) });
  }
}
const pending = {
  buildingEntries: proto.buildings.length - recoveredBuildings,
  maskRecords: proto.masks.length,
  patches: proto.patches.length,
  jumpPairs: proto.jump_line_pairs.length,
  materialRegions: proto.material_sectors.length,
  shadowRegions: proto.light_sectors.length,
};
await fs.mkdir(values.out, { recursive: true });
for (const [asset, p] of packets) {
  p.issues = [...new Set(p.issues)];
  await fs.writeFile(
    path.join(values.out, `${asset}.gameplay-authoring.json`),
    JSON.stringify(p, null, 2) + "\n",
  );
}
const report = {
  status: "incomplete-authoring-recovery",
  assets: packets.size,
  surfaces: [...packets.values()].reduce((sum, p) => sum + p.surfaces.length, 0),
  connections: [...packets.values()].reduce((sum, p) => sum + p.connections.length, 0),
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
