import { MeshoptSimplifier } from "meshoptimizer";
import type { AssetGameplay, AssetWalkableSurface } from "../../shared/src/asset-gameplay.ts";
import { heightPlane } from "../../shared/src/gameplay-plane.ts";
import type { MapCamera, Vec3 } from "../../shared/src/scene.ts";

/** Offline ground authoring from an explicitly selected terrain mesh, in scene coordinates. */
export async function authorMeshGround(
  positions: Float32Array,
  indices: Uint32Array,
  camera: MapCamera,
  options: {
    material: number;
    /** Optional geometric simplification budget, in game units; zero keeps every triangle. */
    simplifyError?: number;
    targetTriangles?: number;
  },
) {
  if (!positions.length || positions.length % 3 || !indices.length || indices.length % 3)
    throw new Error("Ground mesh needs complete vertex and triangle arrays");
  if (!positions.every(Number.isFinite) || indices.some((index) => index >= positions.length / 3))
    throw new Error("Ground mesh has invalid coordinates or vertex indices");
  if (!Number.isInteger(options.material) || options.material < 0 || options.material > 9)
    throw new Error("Ground material must be an explicit native material code from 0 to 9");
  const error = options.simplifyError ?? 0;
  const target = options.targetTriangles ?? 1000;
  if (!Number.isFinite(error) || error < 0 || !Number.isInteger(target) || target < 1)
    throw new Error("Ground simplification needs a nonnegative error and positive triangle target");
  const angle = (camera.elevation_deg * Math.PI) / 180;
  if (!Number.isFinite(angle) || angle <= 0 || angle >= Math.PI / 2)
    throw new Error("Ground camera elevation must be between zero and ninety degrees");
  const points: Vec3[] = [];
  for (let i = 0; i < positions.length; i += 3)
    points.push([
      positions[i]!,
      -positions[i + 1]! * Math.sin(angle),
      positions[i + 2]! * Math.cos(angle),
    ]);
  let authored = indices;
  let simplificationError = 0;
  if (error > 0 && indices.length > target * 3) {
    await MeshoptSimplifier.ready;
    [authored, simplificationError] = MeshoptSimplifier.simplify(
      indices,
      new Float32Array(points.flat()),
      3,
      target * 3,
      error,
      ["LockBorder", "ErrorAbsolute"],
    );
  }
  const surfaces: AssetWalkableSurface[] = [];
  for (let i = 0; i < authored.length; i += 3) {
    const triangle = [...authored.subarray(i, i + 3)].map((index) => points[index]!);
    // A selected ground mesh must support both ground XY and native screen XY height lookup.
    // Do not silently turn vertical faces or folds into a horizontal walkable rectangle.
    heightPlane(triangle);
    heightPlane(triangle.map(([x, y, z]) => [x, y - z, z]));
    surfaces.push({
      id: `mesh-ground-${i / 3}`,
      node: "$root",
      polygon: triangle.map(([x, y]) => [x, y]),
      height: triangle.map((point) => point[2]),
      preserveMovementPrecision: true,
      navigationRegion: "mesh-ground",
      projectionMaterials: { defaultMaterial: options.material, regions: [] },
    });
  }
  const issues = [
    "Ground navigation was derived from the selected terrain mesh. Water, impassable slopes, and material regions have not been authored; the mesh is provisionally walkable and uses one material.",
    ...(authored.length < indices.length
      ? [
          `Ground mesh was simplified from ${indices.length / 3} to ${authored.length / 3} triangles with a ${error}-unit geometric error budget and locked outer borders. Retained vertices preserve mesh elevations; traversal heights and connections still need verification.`,
        ]
      : []),
  ];
  const gameplay: AssetGameplay = {
    version: 1,
    collision: "none",
    surfaces,
    doors: [],
    draft: { issues },
  };
  return {
    gameplay,
    report: {
      sourceTriangles: indices.length / 3,
      authoredTriangles: authored.length / 3,
      simplificationError,
      issues,
    },
  };
}
