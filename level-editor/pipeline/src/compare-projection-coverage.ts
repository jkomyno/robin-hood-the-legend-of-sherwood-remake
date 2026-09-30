import type { MultiPolygon, Polygon } from "polygon-clipping";
import type { CompiledAssetGeometry } from "../../shared/src/asset-gameplay.ts";
import { fixedClipping } from "../../shared/src/fixed-polygon-boolean.ts";
import { heightPlane } from "../../shared/src/gameplay-plane.ts";

function projectionGroups(geometry: CompiledAssetGeometry) {
  const areas = new Map<number, { layer: number; signature: string }>();
  const seenAreas = new Set<string>();
  let sector = 0;
  for (const [layer, members] of geometry.motion_data.layers.entries())
    for (const area of members) {
      const signature = JSON.stringify({ layer, area });
      if (seenAreas.has(signature))
        throw new Error("Projection coverage has ambiguous receiving areas");
      seenAreas.add(signature);
      areas.set(sector, { layer, signature });
      sector += 1 + area.obstacles.length;
    }
  const groups = new Map<string, MultiPolygon>();
  for (const obstacle of geometry.sight_obstacles) {
    if (!Array.isArray(obstacle.projection_area)) continue;
    const [index, layer] = obstacle.projection_area;
    const area = areas.get(index);
    if (!area || area.layer !== layer)
      throw new Error("Projection coverage has an invalid receiving area");
    const { points, projection_area: _projection, material_indices, ...rules } = obstacle;
    const signature = JSON.stringify({
      area: area.signature,
      rules,
      top: heightPlane(points.slice(0, 3).map((p) => [p.x, p.y - p.z_top, p.z_top])),
      bottom: heightPlane(points.slice(0, 3).map((p) => [p.x, p.y - p.z_top, p.z_bottom])),
      materials: material_indices.map((i) => {
        const material = geometry.material_sectors?.[i];
        if (!material) throw new Error("Projection coverage has an invalid material reference");
        return material;
      }),
    });
    const polygon: Polygon = [points.map((p) => [p.x, p.y - p.z_top])];
    const previous = groups.get(signature);
    groups.set(
      signature,
      previous ? fixedClipping.union(previous, polygon) : fixedClipping.union(polygon),
    );
  }
  return groups;
}

const area = (polygons: MultiPolygon) =>
  polygons.reduce(
    (sum, polygon) =>
      sum +
      polygon.reduce(
        (sum, ring, index) =>
          sum +
          ((index ? -1 : 1) *
            Math.abs(
              ring.reduce((total, p, i) => {
                const q = ring[(i + 1) % ring.length]!;
                return total + p[0] * q[1] - q[0] * p[1];
              }, 0),
            )) /
            2,
        0,
      ),
    0,
  );

/** Compare coverage on the compiler's fixed coordinate grid, independently of
 * polygon subdivision and rebuilt motion/material indices. Plane coefficients
 * and rules remain exact. This does not compare overlapping-plane priority,
 * actor traversal, non-projection geometry or state references. */
export function compareProjectionCoverage(
  before: CompiledAssetGeometry,
  after: CompiledAssetGeometry,
) {
  const a = projectionGroups(before),
    b = projectionGroups(after);
  const differences = [];
  for (const signature of new Set([...a.keys(), ...b.keys()])) {
    const old = a.get(signature) ?? [],
      current = b.get(signature) ?? [];
    const removed = current.length ? fixedClipping.difference(old, current) : old;
    const added = old.length ? fixedClipping.difference(current, old) : current;
    if (removed.length || added.length)
      differences.push({
        signature,
        removed,
        added,
        removedArea: area(removed),
        addedArea: area(added),
      });
  }
  return { equal: differences.length === 0, differences };
}
