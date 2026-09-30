import { transformedObstacle, type Level3D } from "../../shared/src/level3d.ts";
import type { ProtoLevel, SightObstacle } from "../../shared/src/level.ts";
import type { ProjectionAssetDescriptor } from "../../shared/src/projection-assets.ts";
import type { RecoveredGameplayPacket } from "./recovered-gameplay-definition.ts";

export interface ReviewedProjections {
  source_sha256: string;
  entries: {
    asset: string;
    model_sha256: string;
    surface: string;
    node: string;
    source_obstacle: number;
  }[];
}

/** One-time migration: source identities validate ownership and never become runtime links. */
export function recoverReviewedProjections(
  document: Level3D,
  descriptors: ReadonlyMap<string, ProjectionAssetDescriptor>,
  source: Pick<ProtoLevel, "sight_obstacles">,
  sourceSha256: string,
  definitions: ReviewedProjections,
  packets: ReadonlyMap<string, RecoveredGameplayPacket>,
) {
  if (definitions.source_sha256 !== sourceSha256)
    throw new Error("Reviewed projection source changed");
  if (!Array.isArray(definitions.entries) || !definitions.entries.length)
    throw new Error("Reviewed projections need entries");
  const seen = new Set<string>();
  const vertices = (shape: SightObstacle) =>
    shape.points.map((p) => [p.x, p.y, p.z_bottom, p.z_top].map(Math.fround));
  const flags = ["solid", "opaque", "mouse", "show_shadow_polygon", "default_material"] as const;
  const updates = definitions.entries.map((entry) => {
    const key = `${entry.asset}/${entry.surface}`;
    if (seen.has(key)) throw new Error(`Duplicate reviewed projection: ${key}`);
    seen.add(key);
    const reference = document.assetSources?.find((a) => a.id === entry.asset);
    if (!reference || reference.model_sha256 !== entry.model_sha256)
      throw new Error(`Reviewed projection model changed: ${entry.asset}`);
    const parts = document.objects.filter((p) => p.node === `asset:${entry.asset}:${entry.node}`);
    const packet = packets.get(entry.asset);
    const surfaces = packet?.surfaces.filter((s) => s.id === entry.surface) ?? [];
    const part = parts[0],
      surface = surfaces[0];
    const definition = descriptors.get(entry.asset)?.parts.find((p) => p.node === entry.node);
    const original = source.sight_obstacles[entry.source_obstacle];
    const owners = new Set(
      document.objects
        .filter((p) => p.source.obstacle === entry.source_obstacle)
        .map((p) => p.node),
    );
    if (
      parts.length !== 1 ||
      surfaces.length !== 1 ||
      !part ||
      !surface ||
      surface.node !== entry.node ||
      !Number.isInteger(entry.source_obstacle) ||
      entry.source_obstacle < 0 ||
      part.source.obstacle !== entry.source_obstacle ||
      owners.size !== 1 ||
      !definition?.obstacle_local_game ||
      definition.mission_profile !== undefined ||
      !Array.isArray(original?.projection_area) ||
      !surface.projectionMaterials ||
      surface.projectionVolume !== undefined
    )
      throw new Error(
        `Reviewed projection requires one physical owner and recovered surface: ${key}`,
      );
    const shape = transformedObstacle(document, {
      ...part,
      obstacle: definition.obstacle_local_game,
    });
    if (
      !flags.every((flag) => shape[flag] === original[flag]) ||
      JSON.stringify(vertices(shape)) !== JSON.stringify(vertices(original))
    )
      throw new Error(`Reviewed projection physical geometry changed: ${key}`);
    const materials = surface.projectionMaterials.regions.map((id) => {
      const matches = packet?.materials?.filter((m) => m.id === id) ?? [];
      if (matches.length !== 1)
        throw new Error(`Reviewed projection material missing or ambiguous: ${key}/${id}`);
      return matches[0]!;
    });
    return { entry, surface, materials };
  });
  // Validate the whole recipe before changing any authoring packet.
  for (const { entry, surface, materials } of updates) {
    for (const material of materials)
      if (!material.obstacles.includes(entry.node)) material.obstacles.push(entry.node);
    delete surface.projectionMaterials;
    surface.projectionVolume = entry.node;
  }
  return updates.map(({ entry }) => ({ ...entry }));
}
