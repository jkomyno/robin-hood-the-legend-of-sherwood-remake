import earcut, { flatten } from "earcut";
import clipping, { type MultiPolygon, type Polygon } from "polygon-clipping";
import { CatmullRomCurve3, Vector3 } from "three";
import { gameToScene, type MapCamera } from "./scene.ts";
import type { Level3D } from "./level3d.ts";
import type { LevelSpline } from "./splines.ts";
import type { Point } from "./level.ts";
import type { GameplayAssetDescriptor, AssetWalkableSurface } from "./asset-gameplay.ts";

/** Later regions replace earlier ground, including when lowering a river bed. */
export interface GroundRegion {
  id: string;
  name: string;
  bounds: [number, number, number, number];
  height: number;
  material: "grass" | "dirt" | "water" | "paved";
}
export interface TerrainPatch {
  id: string;
  height: number;
  material: GroundRegion["material"];
  polygon: Point[];
  holes: Point[][];
}
export function validateGroundRegions(value: unknown): asserts value is GroundRegion[] {
  if (!Array.isArray(value)) throw new Error("Terrain must be an array of regions");
  const ids = new Set<string>();
  for (const region of value) {
    if (
      !region ||
      typeof region.id !== "string" ||
      !region.id ||
      ids.has(region.id) ||
      typeof region.name !== "string" ||
      !Number.isFinite(region.height) ||
      !["grass", "dirt", "water", "paved"].includes(region.material) ||
      !Array.isArray(region.bounds) ||
      region.bounds.length !== 4 ||
      !region.bounds.every(Number.isFinite) ||
      region.bounds[2] < 1 ||
      region.bounds[3] < 1
    )
      throw new Error("Terrain needs unique IDs, a material, finite elevation and positive bounds");
    ids.add(region.id);
  }
}

/** Shared with the visible strip so river boundaries match export and placement. */
export function terrainSplineCurve(path: LevelSpline, camera: MapCamera) {
  const curve = new CatmullRomCurve3(
    path.points.map((p) => new Vector3(...gameToScene(camera, ...p))),
    path.closed,
    "centripetal",
  );
  curve.arcLengthDivisions = Math.max(256, path.points.length * 40);
  curve.updateArcLengths();
  return curve;
}
export function splineFootprint(path: LevelSpline, camera: MapCamera): MultiPolygon {
  const curve = terrainSplineCurve(path, camera),
    length = curve.getLength();
  const count = Math.min(4096, Math.max(8, Math.ceil(length / 12)));
  const sin = Math.sin((camera.elevation_deg * Math.PI) / 180);
  const pairs: [Point, Point][] = [];
  for (let i = 0; i <= count; i++) {
    const p = curve.getPointAt(i / count),
      tangent = curve.getTangentAt(i / count);
    const n = new Vector3(-tangent.y, tangent.x, 0).normalize().multiplyScalar(path.width / 2);
    pairs.push([
      [-n.x + p.x, -(p.y - n.y) * sin],
      [n.x + p.x, -(p.y + n.y) * sin],
    ]);
  }
  const strips: Polygon[] = pairs
    .slice(1)
    .map((pair, i) => [[pairs[i]![0], pairs[i]![1], pair[1], pair[0]]]);
  return clipping.union(strips[0]!, ...strips.slice(1));
}

/** Resolve overlaps once, in ground XY, before projecting each elevation into navigation. */
export function terrainPatches(document: Level3D, strict = true): TerrainPatch[] {
  validateGroundRegions(document.terrain ?? []);
  const layers: {
    id: string;
    height: number;
    material: GroundRegion["material"];
    shape: MultiPolygon;
  }[] = (document.terrain ?? []).map((region) => {
    const [x, y, w, h] = region.bounds;
    return {
      ...region,
      shape: [
        [
          [
            [x, y],
            [x + w, y],
            [x + w, y + h],
            [x, y + h],
          ],
        ],
      ],
    };
  });
  for (const path of document.splines ?? []) {
    if (path.kind === "wall") continue;
    const height = path.points[0]?.[2];
    if (height === undefined || path.points.some((p) => Math.abs(p[2] - height) > 0.001)) {
      if (!strict) continue;
      throw new Error(
        `${path.name}: terrain paths need a uniform elevation; use Set elevation for the whole path`,
      );
    }
    layers.push({
      id: `spline/${path.id}`,
      height,
      material: path.kind === "river" ? "water" : "dirt",
      shape: splineFootprint(path, document.camera),
    });
  }
  return layers.flatMap((layer, i) => {
    const later = layers.slice(i + 1).map((l) => l.shape);
    const shape = later.length
      ? clipping.difference(layer.shape, ...later)
      : clipping.union(layer.shape);
    return shape.map((polygon, j) => ({
      id: `${layer.id}/${j}`,
      height: layer.height,
      material: layer.material,
      polygon: polygon[0]!.slice(0, -1) as Point[],
      holes: polygon.slice(1).map((r) => r.slice(0, -1) as Point[]),
    }));
  });
}

function materialPolygons(patch: TerrainPatch): Point[][] {
  if (!patch.holes.length) return [patch.polygon];
  const { vertices, holes, dimensions } = flatten([patch.polygon, ...patch.holes]);
  const indices = earcut(vertices, holes, dimensions);
  if (!indices.length) throw new Error(`Cannot triangulate terrain material ${patch.id}`);
  const triangles: Point[][] = [];
  for (let i = 0; i < indices.length; i += 3)
    triangles.push(indices.slice(i, i + 3).map((n) => [vertices[n * 2]!, vertices[n * 2 + 1]!]));
  return triangles;
}

export function terrainGameplay(document: Level3D): GameplayAssetDescriptor | undefined {
  const patches = terrainPatches(document);
  if (!patches.length) return undefined;
  const material = { grass: 3, dirt: 0, water: 5, paved: 2 };
  const surface = (p: TerrainPatch): AssetWalkableSurface => ({
    id: p.id,
    node: "$root",
    polygon: p.polygon,
    holes: p.holes,
    height: p.height,
    navigationRegion: `height/${p.height}`,
    projectionMaterials: { defaultMaterial: material[p.material], regions: [] },
  });
  return {
    version: 1,
    kind: "projection-mapped-asset",
    id: "authored-terrain",
    name: "Authored terrain",
    source_map: document.map,
    model: "generated",
    editor_usage: "map-background",
    parts: [],
    gameplay: {
      version: 1,
      collision: "none",
      doors: [],
      surfaces: patches.map(surface),
      materials: patches
        .filter((p) => p.material === "water")
        .flatMap((p) =>
          materialPolygons(p).map((polygon, i) => ({
            id: `material/${p.id}/${i}`,
            node: "$root",
            polygon: polygon.map(([x, y]): [number, number, number] => [x, y, p.height]),
            material: 5,
            ground: true,
            obstacles: [],
          })),
        ),
      movementBlockers: patches
        .filter((p) => p.material === "water")
        .map((p) => ({
          ...surface(p),
          id: `water/${p.id}`,
          navigationRegion: undefined,
          projectionMaterials: undefined,
        })),
    },
  };
}
