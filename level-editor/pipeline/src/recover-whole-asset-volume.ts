import type { ProjectionAssetDescriptor, SightObstacle, Vec3 } from "@rle/shared";
import type { AssetGameplay } from "../../shared/src/asset-gameplay.ts";

/** Restore an explicitly owned volume independently of visual component bounds. */
export function recoverWholeAssetVolume(options: {
  descriptor: ProjectionAssetDescriptor;
  source: SightObstacle;
  sourceIndex: number;
  node: string;
  localize: (point: Vec3) => Vec3;
}): { collision: "none"; volumes: [NonNullable<AssetGameplay["volumes"]>[number]] } {
  const { descriptor, source, sourceIndex, node, localize } = options;
  const parts = descriptor.parts.filter((p) => p.obstacle_local_game);
  if (
    !Number.isInteger(sourceIndex) ||
    sourceIndex < 0 ||
    !parts.length ||
    !parts.some((p) => p.node === node) ||
    parts.some((p) => p.source_obstacle !== sourceIndex || p.mission_profile !== undefined)
  )
    throw new Error("Whole-volume recovery requires exclusive ownership of every physical part");
  if (
    source.projection_area != null ||
    source.projection_plane !== undefined ||
    source.material_indices.length
  )
    throw new Error(
      "Whole-volume receiving geometry and material regions require separate authoring",
    );
  const { projection_area: _projection, material_indices: _materials, ...flags } = source;
  const points = source.points.map((p) => {
    const bottom = localize([p.x, p.y, p.z_bottom]),
      top = localize([p.x, p.y, p.z_top]);
    if (
      bottom.length !== 3 ||
      top.length !== 3 ||
      ![...bottom, ...top].every(Number.isFinite) ||
      Math.hypot(bottom[0] - top[0], bottom[1] - top[1]) > 1e-5
    )
      throw new Error("Whole-volume recovery needs a finite vertical asset frame");
    return { x: top[0], y: top[1], z_bottom: bottom[2], z_top: top[2] };
  });
  return {
    collision: "none",
    volumes: [{ id: `gameplay-volume-${sourceIndex}`, node, shape: { ...flags, points } }],
  };
}
