import type {
  Level3D,
  Level3DObject,
  Vec3,
  ProtoLevel,
  ProjectionAssetDescriptor,
} from "@rle/shared";
import { transformedObstacle } from "../../shared/src/level3d.ts";
import { distanceToPolygon } from "./recovery-elevation.ts";

export interface ReviewedGroundReceivers {
  source_sha256: string;
  entries: {
    asset: string;
    model_sha256: string;
    node: string;
    source_obstacle: number;
    anchor: [number, number];
  }[];
}

/** Validate one-time physical ownership and convert navigation anchors into asset coordinates. */
export function recoverGroundReceivers(
  document: Level3D,
  descriptors: ReadonlyMap<string, ProjectionAssetDescriptor>,
  source: Pick<ProtoLevel, "motion_data" | "sight_obstacles">,
  sourceHash: string,
  definitions: ReviewedGroundReceivers,
  localize: (part: Level3DObject, point: Vec3) => Vec3,
) {
  if (definitions.source_sha256 !== sourceHash) throw new Error("Ground receiver source changed");
  if (!Array.isArray(definitions.entries) || !definitions.entries.length)
    throw new Error("Ground receiver definitions need entries");
  const seen = new Set<number>();
  return definitions.entries.map((entry) => {
    const reference = document.assetSources?.find((a) => a.id === entry.asset);
    const physical = source.sight_obstacles[entry.source_obstacle];
    const parts = document.objects.filter((p) => p.source.obstacle === entry.source_obstacle);
    const part = parts[0];
    const definition = descriptors.get(entry.asset)?.parts.find((p) => p.node === entry.node);
    if (
      !Number.isInteger(entry.source_obstacle) ||
      entry.source_obstacle < 0 ||
      seen.has(entry.source_obstacle) ||
      !reference ||
      reference.model_sha256 !== entry.model_sha256 ||
      parts.length !== 1 ||
      !part ||
      part.node !== `asset:${entry.asset}:${entry.node}` ||
      !definition?.obstacle_local_game ||
      definition.collision === "none" ||
      definition.mission_profile !== undefined ||
      !Array.isArray(physical?.projection_area) ||
      physical.projection_area[1] !== 0
    )
      throw new Error(
        `Ground receiver needs one pinned physical owner: ${entry.asset}/${entry.node}`,
      );
    seen.add(entry.source_obstacle);
    const placed = transformedObstacle(document, {
      ...part,
      obstacle: definition.obstacle_local_game,
    });
    const vertices = (shape: typeof placed) =>
      shape.points.map((p) => [p.x, p.y, p.z_bottom, p.z_top].map(Math.fround));
    const flags = ["solid", "opaque", "mouse", "show_shadow_polygon", "default_material"] as const;
    if (
      JSON.stringify(vertices(placed)) !== JSON.stringify(vertices(physical)) ||
      !flags.every((flag) => placed[flag] === physical[flag])
    )
      throw new Error(`Ground receiver physical geometry changed: ${entry.asset}/${entry.node}`);
    let sector = 0;
    const targetSector = physical.projection_area[0];
    const area = source.motion_data.layers[0]!.find((area) => {
      const matches = sector === targetSector;
      sector += 1 + area.obstacles.length;
      return matches;
    });
    if (
      !area ||
      area.is_lift ||
      area.state_id !== 0 ||
      area.obstacles.some((o) => o.state_id !== 0) ||
      !Array.isArray(entry.anchor) ||
      entry.anchor.length !== 2 ||
      !entry.anchor.every(Number.isFinite) ||
      distanceToPolygon(entry.anchor, area.polygon.points) !== 0 ||
      area.obstacles.some((o) => distanceToPolygon(entry.anchor, o.polygon.points) === 0)
    )
      throw new Error(
        `Ground receiver requires a static unblocked ground anchor: ${entry.asset}/${entry.node}`,
      );
    return { ...entry, localAnchor: localize(part, [...entry.anchor, 0]) };
  });
}
