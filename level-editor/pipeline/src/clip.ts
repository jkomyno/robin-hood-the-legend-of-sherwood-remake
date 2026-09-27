// Clip proto-level metadata to an extraction region and translate it to
// asset-local coordinates (world minus origin).
import pc from "polygon-clipping";
import type { AssetMotion, AssetVolumes, Mask, Point, Polygon, ProtoLevel } from "@rle/shared";

export type Bbox = [number, number, number, number]; // x, y, w, h

function bboxOverlapsPoly(
  bbox: Bbox,
  pts: readonly (readonly [number, number, ...number[]])[],
): boolean {
  if (pts.length === 0) return false;
  const [bx, by, bw, bh] = bbox;
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  for (const [x, y] of pts) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  return maxX >= bx && minX <= bx + bw && maxY >= by && minY <= by + bh;
}

const shift = (pts: readonly Point[], ox: number, oy: number): Point[] =>
  pts.map(([x, y]) => [x - ox, y - oy]);

function clipPolyToBbox(pts: readonly Point[], bbox: Bbox): Point[][] {
  const [bx, by, bw, bh] = bbox;
  const rect: Point[] = [
    [bx, by],
    [bx + bw, by],
    [bx + bw, by + bh],
    [bx, by + bh],
  ];
  try {
    const result = pc.intersection([pts as Point[]], [rect]);
    return result.flat().map((ring) => ring.slice(0, -1) as Point[]);
  } catch {
    // degenerate polygon — fall back to including it whole
    return [pts.slice()];
  }
}

export interface ClippedLevel {
  volumes: AssetVolumes;
  motion: AssetMotion;
  jump_zones: ProtoLevel["jump_zones"];
  jump_line_pairs: ProtoLevel["jump_line_pairs"];
  lifts: ProtoLevel["lifts"];
  material_sectors: { material: number; polygon: Polygon }[];
  occlusion_masks: Pick<Mask, "layer" | "character_polyline" | "projectile_polyline">[];
}

export function clipLevel(level: ProtoLevel, bbox: Bbox): ClippedLevel {
  const [ox, oy] = [bbox[0], bbox[1]];

  const volumes: AssetVolumes = {
    sight_obstacles: level.sight_obstacles
      .filter((so) =>
        bboxOverlapsPoly(
          bbox,
          so.points.map((p) => [p.x, p.y] as Point),
        ),
      )
      .map((so) => ({
        points: so.points.map((p) => ({ ...p, x: p.x - ox, y: p.y - oy })),
        opaque: so.opaque,
        solid: so.solid,
      })),
  };

  const obstacles: AssetMotion["obstacles"] = [];
  const walkable: AssetMotion["walkable"] = [];
  level.motion_data.layers.forEach((areas, layer) => {
    for (const area of areas) {
      for (const obs of area.obstacles) {
        if (bboxOverlapsPoly(bbox, obs.polygon.points))
          obstacles.push({ layer, polygon: { points: shift(obs.polygon.points, ox, oy) } });
      }
      if (bboxOverlapsPoly(bbox, area.polygon.points)) {
        for (const frag of clipPolyToBbox(area.polygon.points, bbox))
          walkable.push({ layer, polygon: { points: shift(frag, ox, oy) } });
      }
    }
  });

  const shiftedLift = new Set<number>();
  const selectedPairs = level.jump_line_pairs.filter(
    (p) =>
      bboxOverlapsPoly(bbox, [p.line1.point_a, p.line1.point_b]) ||
      bboxOverlapsPoly(bbox, [p.line2.point_a, p.line2.point_b]),
  );
  const requiredZones = new Set(
    selectedPairs.flatMap((p) => [p.line1.jump_zone_index, p.line2.jump_zone_index]),
  );
  for (const index of requiredZones)
    if (!level.jump_zones[index]) throw new Error(`Jump pair references missing zone ${index}`);
  const zoneIndices = new Map<number, number>();
  const jumpZones = level.jump_zones.flatMap((zone, index) => {
    if (!requiredZones.has(index) && !bboxOverlapsPoly(bbox, zone.polygon.points)) return [];
    zoneIndices.set(index, zoneIndices.size);
    return [{ ...zone, polygon: { points: shift(zone.polygon.points, ox, oy) } }];
  });
  const shiftJump = ([x, y, z]: [number, number, number]): [number, number, number] => {
    if (!Number.isFinite(z)) throw new Error("Jump edge is missing its elevation");
    return [x - ox, y - oy, z];
  };
  const jumpPairs = selectedPairs.map((p) => ({
    ...p,
    line1: {
      ...p.line1,
      point_a: shiftJump(p.line1.point_a),
      point_b: shiftJump(p.line1.point_b),
      jump_zone_index: zoneIndices.get(p.line1.jump_zone_index)!,
    },
    line2: {
      ...p.line2,
      point_a: shiftJump(p.line2.point_a),
      point_b: shiftJump(p.line2.point_b),
      jump_zone_index: zoneIndices.get(p.line2.jump_zone_index)!,
    },
  }));

  level.motion_data.layers.forEach((areas) => {
    areas.forEach((area, i) => {
      if (area.is_lift && bboxOverlapsPoly(bbox, area.polygon.points)) shiftedLift.add(i);
    });
  });
  const lifts = level.lifts.filter((l) => shiftedLift.has(l.motion_area_index));

  const materialSectors = level.material_sectors
    .filter((ms) => bboxOverlapsPoly(bbox, ms.polygon.points))
    .flatMap((ms) =>
      clipPolyToBbox(ms.polygon.points, bbox).map((frag) => ({
        material: ms.material,
        polygon: { points: shift(frag, ox, oy) },
      })),
    );

  const occlusionMasks = level.masks
    .filter((m) => {
      const [mx, my] = m.box_top_left;
      const [mw, mh] = m.box_size;
      return bboxOverlapsPoly(bbox, [
        [mx, my],
        [mx + mw, my + mh],
      ]);
    })
    .map((m) => ({
      layer: m.layer,
      character_polyline: shift(m.character_polyline ?? [], ox, oy),
      projectile_polyline: shift(m.projectile_polyline ?? [], ox, oy),
    }));

  return {
    volumes,
    motion: { obstacles, walkable },
    jump_zones: jumpZones,
    jump_line_pairs: jumpPairs,
    lifts,
    material_sectors: materialSectors,
    occlusion_masks: occlusionMasks,
  };
}
