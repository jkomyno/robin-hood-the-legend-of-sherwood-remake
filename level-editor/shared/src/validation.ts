import { componentIdentityMatches, obstaclePartIdentity } from "./component-parts.ts";
import { validatePopulation } from "./population.ts";
import {
  safeLibraryPath,
  type ExternalAssetSource,
  type ProjectionAssetDescriptor,
  type ProjectionAssetEntry,
} from "./projection-assets.ts";
import type { Level3D } from "./level3d.ts";
import type { ProtoLevel } from "./level.ts";
import type { SceneDoc } from "./scene.ts";
import type { AssetDescriptor } from "./asset.ts";
import type { TerrainSpec } from "./terrain.ts";

export function parseTerrainSpec(value: unknown): TerrainSpec {
  const d = object(value, "terrain");
  const points = (v: unknown, path: string) =>
    array(v, path).forEach((p, i) => tuple(p, 2, `${path}[${i}]`));
  for (const [i, road] of array(d.roads === undefined ? [] : d.roads, "terrain.roads").entries()) {
    object(road, "road");
    points(road.points, `terrain.roads[${i}].points`);
    finite(road.width, "road.width");
    check(road.width > 0, "road.width", "must be positive");
  }
  for (const region of array(d.regions === undefined ? [] : d.regions, "terrain.regions")) {
    object(region, "region");
    check(
      ["grass", "dirt", "canopy", "water"].includes(region.material),
      "region.material",
      "unsupported material",
    );
    points(region.polygon, "region.polygon");
  }
  for (const wall of array(d.walls === undefined ? [] : d.walls, "terrain.walls")) {
    object(wall, "wall");
    text(wall.asset, "wall.asset");
    points(wall.points, "wall.points");
    if (wall.segment_set !== undefined)
      array(wall.segment_set, "wall.segment_set").forEach((id) => text(id, "wall.segment_set[]"));
    if (wall.spacing !== undefined) {
      finite(wall.spacing, "wall.spacing");
      check(wall.spacing > 0, "wall.spacing", "must be positive");
    }
  }
  if (d.swatches !== undefined) {
    for (const [role, id] of Object.entries(object(d.swatches, "terrain.swatches"))) {
      check(
        ["grass", "dirt", "road", "canopy", "water"].includes(role),
        "terrain.swatches",
        `unknown role ${role}`,
      );
      text(id, `terrain.swatches.${role}`);
    }
  }
  return value as TerrainSpec;
}

/** Validate fields used by library transforms while preserving exporter extras. */
export function parseAssetDescriptor(value: unknown): AssetDescriptor {
  const d = object(value, "asset");
  for (const key of ["id", "name"]) text(d[key], `asset.${key}`);
  check(
    !/[\\/\0]/.test(d.id) && d.id !== "." && d.id !== "..",
    "asset.id",
    "expected filename component",
  );
  array(d.tags, "asset.tags").forEach((tag) => text(tag, "asset.tags[]"));
  check(
    ["unique", "variant", "spline-segment", "texture"].includes(d.scale_class),
    "asset.scale_class",
    "unsupported scale class",
  );
  tuple(d.origin, 2, "asset.origin");
  tuple(d.anchor, 2, "asset.anchor");
  const source = object(d.source, "asset.source");
  text(source.map, "asset.source.map");
  text(source.ambiance, "asset.source.ambiance");
  tuple(source.bbox, 4, "asset.source.bbox");
  check(
    source.bbox[2] > 0 && source.bbox[3] > 0,
    "asset.source.bbox",
    "dimensions must be positive",
  );
  text(object(source.extraction, "asset.source.extraction").tool, "asset.source.extraction.tool");
  const images = object(d.images, "asset.images");
  for (const key of ["day", "mask"]) text(images[key], `asset.images.${key}`);
  for (const key of ["fog", "night"])
    if (images[key] !== undefined) text(images[key], `asset.images.${key}`);
  const volumes = object(d.volumes, "asset.volumes");
  array(volumes.sight_obstacles, "asset.volumes.sight_obstacles").forEach((v) => {
    object(v, "volume");
    for (const key of ["opaque", "solid"])
      check(typeof v[key] === "boolean", `volume.${key}`, "expected boolean");
    array(v.points, "volume.points").forEach((p) => {
      object(p, "volume.point");
      for (const key of ["x", "y", "z_bottom", "z_top"]) finite(p[key], `volume.point.${key}`);
    });
  });
  const motion = object(d.motion, "asset.motion");
  for (const key of ["obstacles", "walkable"])
    array(motion[key], `asset.motion.${key}`).forEach((v) => {
      object(v, "motion polygon");
      finite(v.layer, "motion.layer");
      array(object(v.polygon, "motion.polygon").points, "motion.polygon.points").forEach((p) =>
        tuple(p, 2, "motion.point"),
      );
    });
  if (d.wall_direction_deg !== undefined) finite(d.wall_direction_deg, "asset.wall_direction_deg");
  if (d.fx !== undefined) {
    const fx = object(d.fx, "asset.fx");
    for (const key of ["bank", "profile", "action"]) text(fx[key], `asset.fx.${key}`);
    tuple(fx.position, 2, "asset.fx.position");
    tuple(fx.hotspot, 2, "asset.fx.hotspot");
    finite(fx.elevation, "asset.fx.elevation");
    check(
      Number.isInteger(fx.frame_count) && fx.frame_count > 0,
      "asset.fx.frame_count",
      "expected positive frame count",
    );
  }
  if (d.merged_from !== undefined)
    array(d.merged_from, "asset.merged_from").forEach((id) => text(id, "asset.merged_from[]"));
  for (const model of [
    d.model,
    ...Object.values(d.alt_models === undefined ? {} : object(d.alt_models, "asset.alt_models")),
  ]) {
    if (model === undefined) continue;
    const m = object(model, "asset.model");
    text(m.glb, "model.glb");
    check(typeof m.textured === "boolean", "model.textured", "expected boolean");
    if (m.pose_l2c !== undefined) {
      const pose = object(m.pose_l2c, "model.pose_l2c");
      tuple(pose.rotation, 4, "model.pose_l2c.rotation");
      tuple(pose.translation, 3, "model.pose_l2c.translation");
      tuple(pose.scale, 3, "model.pose_l2c.scale");
    }
    finite(m.fit_iou, "model.fit_iou");
    if (m.fit_appearance !== undefined) finite(m.fit_appearance, "model.fit_appearance");
    const bounds = object(m.bounds_local, "model.bounds_local");
    tuple(bounds.min, 3, "model.bounds_local.min");
    tuple(bounds.max, 3, "model.bounds_local.max");
    const p = object(m.placement, "model.placement");
    text(p.asset, "model.placement.asset");
    tuple(p.position, 3, "model.placement.position");
    tuple(p.rotation, 4, "model.placement.rotation");
    finite(p.scale, "model.placement.scale");
    check(p.scale > 0, "model.placement.scale", "must be positive");
    const extraction = object(m.extraction, "model.extraction");
    text(extraction.tool, "model.extraction.tool");
    tuple(extraction.crop, 4, "model.extraction.crop");
  }
  return value as AssetDescriptor;
}

function object(v: unknown, path: string): Record<string, any> {
  if (!v || typeof v !== "object" || Array.isArray(v)) throw new Error(`${path}: expected object`);
  return v as Record<string, any>;
}
function check(ok: unknown, path: string, message: string): asserts ok {
  if (!ok) throw new Error(`${path}: ${message}`);
}
function finite(v: unknown, path: string) {
  check(typeof v === "number" && Number.isFinite(v), path, "expected finite number");
}
function text(v: unknown, path: string) {
  check(typeof v === "string" && v.length > 0, path, "expected nonempty string");
}
function array(v: unknown, path: string): any[] {
  check(Array.isArray(v), path, "expected array");
  return v;
}
function tuple(v: unknown, n: number, path: string) {
  const a = array(v, path);
  check(a.length === n, path, `expected ${n} coordinates`);
  a.forEach((x, i) => finite(x, `${path}[${i}]`));
}
function camera(v: unknown, path: string) {
  const c = object(v, path);
  check(c.kind === "oblique-orthographic", path, "unsupported camera");
  finite(c.elevation_deg, path);
  check(
    c.elevation_deg > 0 && c.elevation_deg < 90,
    path,
    "elevation must be between 0 and 90 degrees",
  );
}
function base(v: unknown, path: string) {
  const d = object(v, path);
  check(d.version === 1, path, `unsupported version ${d.version}`);
  text(d.map, `${path}.map`);
  if (d.size !== null) {
    tuple(d.size, 2, `${path}.size`);
    check(
      d.size.every((x: number) => x > 0),
      path,
      "size must be positive",
    );
  }
  camera(d.camera, `${path}.camera`);
  return d;
}
function obstacle(v: unknown, path: string) {
  const o = object(v, path);
  array(o.points, `${path}.points`).forEach((p, i) => {
    object(p, path);
    for (const k of ["x", "y", "z_bottom", "z_top"]) finite(p[k], `${path}.points[${i}].${k}`);
    check(p.z_bottom <= p.z_top, path, "inverted obstacle height");
  });
  for (const k of ["opaque", "solid", "mouse", "show_shadow_polygon"])
    check(typeof o[k] === "boolean", `${path}.${k}`, "expected boolean");
  finite(o.default_material, `${path}.default_material`);
  array(o.material_indices, `${path}.material_indices`).forEach((x) =>
    check(Number.isInteger(x) && x >= 0, path, "invalid material index"),
  );
}
function transform(v: unknown, path: string) {
  const t = object(v, path);
  for (const k of ["dx", "dy", "dz", "rot_deg"]) finite(t[k], `${path}.${k}`);
}

function elementFx(value: unknown, path: string) {
  const fx = object(value, path);
  const sprite = object(fx.sprite, `${path}.sprite`);
  // Empty names are serialized for inactive/no-sprite FX; require strings,
  // without rejecting the converter's legitimate absence representation.
  for (const key of ["frame_profile_name", "profile_name"]) {
    check(typeof sprite[key] === "string", `${path}.sprite.${key}`, "expected string");
  }
  for (const key of ["position_x", "position_y", "elevation"])
    finite(sprite[key], `${path}.sprite.${key}`);
  finite(fx.blit_type, `${path}.blit_type`);
  for (const key of ["active", "force_display"])
    check(typeof fx[key] === "boolean", `${path}.${key}`, "expected boolean");
  array(fx.display_polyline, `${path}.display_polyline`).forEach((point, i) =>
    tuple(point, 2, `${path}.display_polyline[${i}]`),
  );
}

/** Validate in place: unknown Rust/exporter fields survive every round trip. */
export function parseProtoLevel(value: unknown): ProtoLevel {
  const d = object(value, "level");
  check(
    d.format === "Demo" || d.format === "Fullgame",
    "level.format",
    `unsupported Rust level format ${d.format}`,
  );
  array(d.sight_obstacles, "level.sight_obstacles").forEach((o, i) =>
    obstacle(o, `level.sight_obstacles[${i}]`),
  );
  for (const k of [
    "patches",
    "animations",
    "material_sectors",
    "light_sectors",
    "elevation_lines",
    "masks",
    "sound_sources",
    "jump_zones",
    "jump_line_pairs",
    "lifts",
    "buildings",
  ])
    array(d[k], `level.${k}`);
  d.animations.forEach((fx: unknown, i: number) => elementFx(fx, `level.animations[${i}]`));
  d.patches.forEach((value: unknown, i: number) => {
    const path = `level.patches[${i}]`;
    const patch = object(value, path);
    for (const key of ["active", "integrate_in_background"])
      check(typeof patch[key] === "boolean", `${path}.${key}`, "expected boolean");
    elementFx(patch.element_fx, `${path}.element_fx`);
  });
  d.elevation_lines.forEach((e: any, i: number) => {
    object(e, "elevation line");
    tuple(e.point_a, 2, `elevation_lines[${i}].point_a`);
    tuple(e.point_b, 2, `elevation_lines[${i}].point_b`);
  });
  const polygon = (p: unknown, path: string) =>
    array(object(p, path).points, `${path}.points`).forEach((point, i) =>
      tuple(point, 2, `${path}.points[${i}]`),
    );
  for (const key of ["material_sectors", "light_sectors", "jump_zones"])
    d[key].forEach((item: any, i: number) =>
      polygon(object(item, key).polygon, `${key}[${i}].polygon`),
    );
  d.material_sectors.forEach((item: any, i: number) =>
    finite(item.material, `material_sectors[${i}].material`),
  );
  d.masks.forEach((mask: any, i: number) => {
    object(mask, "mask");
    tuple(mask.box_top_left, 2, `masks[${i}].box_top_left`);
    tuple(mask.box_size, 2, `masks[${i}].box_size`);
    // Each polyline is null unless the matching mask_type bit is set.
    for (const key of ["character_polyline", "projectile_polyline"]) {
      if (mask[key] === null) continue;
      array(mask[key], `masks[${i}].${key}`).forEach((point, j) =>
        tuple(point, 2, `masks[${i}].${key}[${j}]`),
      );
    }
    array(mask.obstacle_indices, `masks[${i}].obstacle_indices`).forEach((index) =>
      check(
        Number.isInteger(index) && index >= 0 && index < d.sight_obstacles.length,
        `masks[${i}]`,
        "dangling obstacle index",
      ),
    );
    array(mask.mask_data, `masks[${i}].mask_data`);
  });
  object(d.misc, "level.misc");
  object(d.motion_data, "level.motion_data");
  array(d.motion_data.layers, "level.motion_data.layers");
  array(d.motion_data.graph_bytes, "level.motion_data.graph_bytes");
  d.motion_data.layers.forEach((layer: unknown, i: number) =>
    array(layer, `motion_data.layers[${i}]`).forEach((area) => {
      polygon(object(area, "motion area").polygon, "motion area.polygon");
      array(area.obstacles, "motion area.obstacles").forEach((o) =>
        polygon(object(o, "motion obstacle").polygon, "motion obstacle.polygon"),
      );
    }),
  );
  return value as ProtoLevel;
}

export function parseSceneDoc(value: unknown): SceneDoc {
  const d = base(value, "scene");
  if (d.size === null)
    check(d.standalone === true, "scene.size", "unbounded scenes must be standalone");
  if (d.standalone !== undefined)
    check(typeof d.standalone === "boolean", "scene.standalone", "expected boolean");
  array(d.placements, "scene.placements").forEach((p, i) => {
    object(p, "placement");
    text(p.asset, `placements[${i}].asset`);
    tuple(p.position, 3, "placement.position");
    tuple(p.rotation, 4, "placement.rotation");
    finite(p.scale, "placement.scale");
    check(p.scale > 0, "placement.scale", "must be positive");
  });
  if (d.ground) {
    text(d.ground.texture, "ground.texture");
    tuple(d.ground.rect, 4, "ground.rect");
  }
  return value as SceneDoc;
}

export interface DocumentContext {
  scene?: Pick<SceneDoc, "size" | "camera">;
  map?: string;
  level?: ProtoLevel;
  nodes?: ReadonlySet<string>;
  sourceSha256?: string;
}

/** Source hash uses the complete parsed export, including unknown fields, in JSON key order. */
export async function documentProvenance(level: ProtoLevel | null) {
  const hash = async (bytes: ArrayBuffer) =>
    Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), (b) =>
      b.toString(16).padStart(2, "0"),
    ).join("");
  return {
    source_sha256: level
      ? await hash(new TextEncoder().encode(JSON.stringify(level)).buffer)
      : undefined,
  };
}

export function parseLevel3D(value: unknown, context: DocumentContext = {}): Level3D {
  const d = base(value, "level3d");
  if (d.exportBounds !== undefined) {
    tuple(d.exportBounds, 4, "level3d.exportBounds");
    check(
      d.exportBounds.every(Number.isInteger) && d.exportBounds[2] > 0 && d.exportBounds[3] > 0,
      "level3d.exportBounds",
      "expected integer origin and positive integer dimensions",
    );
  }
  if (context.scene) {
    check(
      d.size === null || context.scene.size === null
        ? d.size === context.scene.size
        : d.size[0] === context.scene.size[0] && d.size[1] === context.scene.size[1],
      "level3d.size",
      "does not match source scene",
    );
    check(
      d.camera.elevation_deg === context.scene.camera.elevation_deg,
      "level3d.camera",
      "does not match source scene",
    );
  }
  check(
    d.glb === undefined,
    "level3d.glb",
    "whole-map models must be imported into sceneAssets before opening",
  );
  if (d.sceneMetadata !== undefined) object(d.sceneMetadata, "sceneMetadata");
  const sceneIds = new Set<string>();
  let grounds = 0;
  for (const asset of array(d.sceneAssets, "level3d.sceneAssets")) {
    object(asset, "scene asset");
    text(asset.id, "scene asset.id");
    check(!sceneIds.has(asset.id), asset.id, "duplicate scene asset");
    sceneIds.add(asset.id);
    check(
      asset.role === "ground" || asset.role === "objects" || asset.role === "metadata",
      asset.id,
      "invalid scene asset role",
    );
    if (asset.role === "ground") grounds++;
    if (asset.model_scene !== undefined) text(asset.model_scene, "scene asset.model_scene");
    if (asset.descriptor !== undefined || asset.descriptor_sha256 !== undefined) {
      check(safeLibraryPath(asset.descriptor), asset.id, "unsafe scene asset descriptor");
      check(
        typeof asset.descriptor_sha256 === "string" &&
          /^[a-f0-9]{64}$/.test(asset.descriptor_sha256),
        asset.id,
        "invalid descriptor hash",
      );
    }
    check(safeLibraryPath(asset.model), asset.id, "unsafe scene asset model");
    check(/^[a-f0-9]{64}$/.test(asset.model_sha256), asset.id, "invalid scene asset model hash");
    const paths = new Set<string>();
    for (const resource of array(asset.resources, "scene asset.resources")) {
      object(resource, "scene resource");
      check(
        safeLibraryPath(resource.path) && !paths.has(resource.path),
        asset.id,
        "unsafe or duplicate scene resource",
      );
      paths.add(resource.path);
      check(/^[a-f0-9]{64}$/.test(resource.sha256), asset.id, "invalid scene resource hash");
    }
  }
  check(grounds <= 1, "sceneAssets", "multiple ground assets");
  if (d.sourceMap !== undefined) text(d.sourceMap, "level3d.sourceMap");
  if (context.map)
    check(
      d.map.toLowerCase() === context.map.toLowerCase(),
      "level3d.map",
      `expected source ${context.map}, got ${d.map}`,
    );

  if (d.assetSources !== undefined) parseExternalAssetSources(d.assetSources);
  const assetIds = new Set((d.assetSources ?? []).map((entry: ExternalAssetSource) => entry.id));
  const ids = new Set<string>();
  const groups = new Set<string>();
  for (const g of array(d.groups, "level3d.groups")) {
    object(g, "level3d.groups[]");
    text(g.id, "group.id");
    check(!ids.has(g.id), g.id, "duplicate ID");
    ids.add(g.id);
    groups.add(g.id);
    transform(g.transform, g.id);
    if (g.hidden !== undefined) check(typeof g.hidden === "boolean", g.id, "invalid hidden flag");
  }
  for (const o of array(d.objects, "level3d.objects")) {
    object(o, "level3d.objects[]");
    text(o.id, "object.id");
    if (o.missionBindings !== undefined) {
      object(o.missionBindings, "missionBindings");
      for (const [name, values] of Object.entries(o.missionBindings)) {
        text(name, "mission binding node");
        object(values, "mission binding metadata");
      }
    }
    check(!ids.has(o.id), o.id, "duplicate ID");
    ids.add(o.id);
    check(
      o.kind === "building" || o.kind === "terrace" || o.kind === "mission",
      o.id,
      "unsupported kind",
    );
    text(o.node, `${o.id}.node`);
    if (o.node.startsWith("asset:")) {
      const match =
        /^asset:([^:]+):((?:building|terrace)-\d+(?:--component-[a-zA-Z0-9_-]+)?|mission-[a-zA-Z0-9_-]+)$/.exec(
          o.node,
        );
      check(!!match && assetIds.has(match[1]!), o.id, "dangling external asset source");
      if (!match[2]!.startsWith("mission-"))
        check(
          componentIdentityMatches(match[2]!, o.source?.obstacle, o.source?.components),
          o.id,
          "external asset canonical obstacle mismatch",
        );
      else check(o.kind === "mission", o.id, "mission source requires mission kind");
    }
    if (context.nodes) check(context.nodes.has(o.node), o.id, `missing source node ${o.node}`);
    object(o.source, `${o.id}.source`);
    text(o.source.map, `${o.id}.source.map`);
    if (!o.node.startsWith("asset:")) check(o.source.map === d.map, o.id, "mismatched source map");
    if (o.kind === "mission") {
      check(
        o.source.obstacle === undefined && /^(?:asset:[^:]+:)?mission-[a-zA-Z0-9_-]+$/.test(o.node),
        o.id,
        "mission parts cannot claim an obstacle index",
      );
      text(o.source.mission_profile, `${o.id}.source.mission_profile`);
    } else {
      check(
        Number.isInteger(o.source.obstacle) &&
          o.source.obstacle >= 0 &&
          o.source.mission_profile === undefined,
        o.id,
        "invalid obstacle index or mission profile",
      );
      if (
        !o.node.startsWith("asset:") &&
        (o.source.components !== undefined || o.node.includes("--component-"))
      )
        check(
          componentIdentityMatches(o.node, o.source.obstacle, o.source.components),
          o.id,
          "component identity mismatch",
        );
      if (context.level && !o.node.startsWith("asset:"))
        check(
          o.source.obstacle < context.level.sight_obstacles.length,
          o.id,
          "dangling obstacle index",
        );
    }
    if (o.group !== undefined) check(groups.has(o.group), o.id, `dangling group ${o.group}`);
    if (o.hidden !== undefined) check(typeof o.hidden === "boolean", o.id, "invalid hidden flag");
    obstacle(o.obstacle, `${o.id}.obstacle`);
    check(o.obstacle.points.length >= 3, o.id, "editable obstacle needs at least three points");
    transform(o.transform, o.id);
  }
  for (const group of d.groups)
    if (group.states !== undefined) {
      const members = d.objects.filter((part: any) => part.group === group.id);
      validateAssetStates(
        group.states,
        new Map(members.map((part: any) => [part.id, !!part.hidden])),
        group.id,
      );
    }
  if (d.lighting !== undefined) {
    const light = object(d.lighting, "lighting");
    check(typeof light.enabled === "boolean", "lighting.enabled", "expected boolean");
    finite(light.sunAzimuth, "lighting.sunAzimuth");
    finite(light.sunElevation, "lighting.sunElevation");
    finite(light.shadowOpacity, "lighting.shadowOpacity");
    check(
      light.sunAzimuth >= 0 && light.sunAzimuth <= 360,
      "lighting.sunAzimuth",
      "expected 0–360 degrees",
    );
    check(
      light.sunElevation >= 10 && light.sunElevation <= 85,
      "lighting.sunElevation",
      "expected 10–85 degrees",
    );
    check(
      light.shadowOpacity >= 0 && light.shadowOpacity <= 1,
      "lighting.shadowOpacity",
      "expected 0–1",
    );
  }
  if (d.population !== undefined) validatePopulation(d.population);
  const splineIds = new Set<string>();
  if (d.splines !== undefined)
    for (const spline of array(d.splines, "splines")) {
      object(spline, "spline");
      text(spline.id, "spline.id");
      text(spline.name, "spline.name");
      check(!splineIds.has(spline.id), spline.id, "duplicate spline");
      splineIds.add(spline.id);
      check(
        spline.kind === "river" || spline.kind === "road" || spline.kind === "wall",
        spline.id,
        "invalid spline kind",
      );
      check(typeof spline.closed === "boolean", spline.id, "closed must be boolean");
      finite(spline.width, "spline.width");
      finite(spline.repeatLength, "spline.repeatLength");
      check(
        spline.width > 0 && spline.repeatLength >= 1,
        spline.id,
        "invalid width or repeat length",
      );
      const points = array(spline.points, "spline.points");
      check(
        points.length >= (spline.closed ? 3 : 2) && points.length <= 256,
        spline.id,
        "expected 2–256 control points (3 for closed paths)",
      );
      points.forEach((point, index) => {
        tuple(point, 3, "spline.point");
        if (index)
          check(
            Math.hypot(point[0] - points[index - 1][0], point[1] - points[index - 1][1]) > 0.01,
            spline.id,
            "adjacent control points must differ",
          );
      });
      if (spline.texture !== undefined)
        check(
          typeof spline.texture === "string" &&
            /^data:image\/(png|jpeg|webp);base64,/.test(spline.texture),
          spline.id,
          "expected embedded PNG, JPEG or WebP tile",
        );
      if (spline.kind === "wall") {
        check(assetIds.has(spline.asset), spline.id, "missing wall asset source");
        check(spline.axis === "x" || spline.axis === "y", spline.id, "invalid source axis");
        if (spline.flipCrossSection !== undefined)
          check(
            typeof spline.flipCrossSection === "boolean",
            spline.id,
            "flipCrossSection must be boolean",
          );
        if (spline.sourceAngle !== undefined) finite(spline.sourceAngle, "spline.sourceAngle");
        if (spline.cornerAsset !== undefined) {
          check(assetIds.has(spline.cornerAsset), spline.id, "missing corner tower asset source");
          const angle = spline.cornerMinAngle ?? 35,
            scale = spline.cornerScale ?? 1;
          finite(angle, "spline.cornerMinAngle");
          finite(scale, "spline.cornerScale");
          check(
            angle > 0 && angle < 180 && scale > 0 && scale <= 10,
            spline.id,
            "invalid corner angle or scale",
          );
          if (spline.cornerWidthScale !== undefined) {
            finite(spline.cornerWidthScale, "spline.cornerWidthScale");
            check(
              spline.cornerWidthScale > 0 && spline.cornerWidthScale <= 10,
              spline.id,
              "invalid corner width scale",
            );
          }
          if (spline.cornerRotation !== undefined)
            finite(spline.cornerRotation, "spline.cornerRotation");
          if (spline.cornerDisabled !== undefined)
            for (const index of array(spline.cornerDisabled, "spline.cornerDisabled"))
              check(
                Number.isInteger(index) && index >= 0 && index < points.length,
                spline.id,
                "invalid disabled corner index",
              );
        }
        const start = spline.sourceStart ?? 0,
          end = spline.sourceEnd ?? 1;
        finite(start, "spline.sourceStart");
        finite(end, "spline.sourceEnd");
        check(
          start >= 0 && end <= 1 && end - start >= 0.05,
          spline.id,
          "invalid source trim interval",
        );
      }
    }
  if (d.provenance !== undefined) {
    const p = object(d.provenance, "provenance");
    for (const [key, expected] of [["source_sha256", context.sourceSha256]]) {
      if (p[key!] !== undefined) {
        check(
          typeof p[key!] === "string" && /^[a-f0-9]{64}$/.test(p[key!]),
          `provenance.${key}`,
          "expected SHA-256",
        );
        if (expected)
          check(
            p[key!] === expected,
            `provenance.${key}`,
            "source content changed; regenerate or explicitly migrate the document",
          );
      }
    }
  }
  return value as Level3D;
}

function validateResources(value: unknown) {
  const paths = new Set<string>();
  for (const resource of array(value, "resources")) {
    object(resource, "resource");
    check(
      safeLibraryPath(resource.path) && !paths.has(resource.path),
      "resource.path",
      "unsafe or duplicate resource",
    );
    check(/^[a-f0-9]{64}$/.test(resource.sha256), "resource.sha256", "invalid hash");
    paths.add(resource.path);
  }
}

export function parseExternalAssetSources(value: unknown): ExternalAssetSource[] {
  const ids = new Set<string>();
  for (const entry of array(value, "assetSources")) {
    object(entry, "assetSources[]");
    if (entry.resources !== undefined) validateResources(entry.resources);
    if (entry.model_scene !== undefined)
      check(
        typeof entry.model_scene === "string" && !!entry.model_scene.trim(),
        "model_scene",
        "expected nonempty scene name",
      );
    if (entry.state_variant !== undefined)
      check(
        entry.state_variant === "initial" || entry.state_variant === "applied",
        "asset source state_variant",
        "invalid static variant",
      );
    text(entry.id, "asset source id");
    check(
      !/[\\/:\0]/.test(entry.id) && !ids.has(entry.id),
      "asset source id",
      "invalid or duplicate identity",
    );
    ids.add(entry.id);
    for (const key of ["descriptor", "model"])
      check(safeLibraryPath(entry[key]), key, "expected safe library-relative path");
    if (entry.preview_model !== undefined)
      check(
        safeLibraryPath(entry.preview_model),
        "preview_model",
        "expected safe library-relative path",
      );
    for (const key of ["descriptor_sha256", "model_sha256"])
      check(
        typeof entry[key] === "string" && /^[a-f0-9]{64}$/.test(entry[key]),
        key,
        "expected SHA-256",
      );
  }
  return value as ExternalAssetSource[];
}

export function parseProjectionAssetIndex(value: unknown): ProjectionAssetEntry[] {
  const index = object(value, "projection asset index");
  check(index.version === 1, "projection asset index", "unsupported version");
  const ids = new Set<string>();
  for (const entry of array(index.assets, "projection asset index.assets")) {
    object(entry, "projection asset entry");
    if (entry.editor_usage !== undefined)
      check(
        entry.editor_usage === "map-background",
        "editor_usage",
        "unsupported asset capability",
      );
    for (const key of ["id", "name", "source_map"]) text(entry[key], key);
    if (entry.model_scene !== undefined)
      check(
        typeof entry.model_scene === "string" && !!entry.model_scene.trim(),
        "model_scene",
        "expected nonempty scene name",
      );
    if (entry.asset_type !== undefined) text(entry.asset_type, "asset_type");
    if (entry.tags !== undefined) for (const tag of array(entry.tags, "tags")) text(tag, "tag");
    check(
      !/[\\/:\0]/.test(entry.id) && !ids.has(entry.id),
      "asset id",
      "invalid or duplicate identity",
    );
    ids.add(entry.id);
    for (const key of ["descriptor", "model"])
      check(safeLibraryPath(entry[key]), key, "expected safe library-relative path");
    for (const key of ["preview_model", "lossy_model"])
      if (entry[key] !== undefined)
        check(safeLibraryPath(entry[key]), key, "expected safe library-relative path");
  }
  return index.assets as ProjectionAssetEntry[];
}

export function parseProjectionAssetDescriptor(value: unknown): ProjectionAssetDescriptor {
  const d = object(value, "projection asset");
  check(
    d.version === 1 && d.kind === "projection-mapped-asset",
    "projection asset",
    "unsupported kind/version",
  );
  for (const key of ["id", "name", "source_map"]) text(d[key], key);
  if (d.source_origin_scene !== undefined)
    check(
      Array.isArray(d.source_origin_scene) &&
        d.source_origin_scene.length === 3 &&
        d.source_origin_scene.every(
          (value: unknown) => typeof value === "number" && Number.isFinite(value),
        ),
      "asset.source_origin_scene",
      "expected three finite coordinates",
    );
  check(!/[\\/:\0]/.test(d.id), "asset id", "invalid identity");
  if (d.model_scene !== undefined)
    check(
      typeof d.model_scene === "string" && !!d.model_scene.trim(),
      "asset.model_scene",
      "expected nonempty scene name",
    );
  check(safeLibraryPath(d.model), "asset.model", "expected safe relative path");
  if (d.resources !== undefined) validateResources(d.resources);
  const nodes = new Set<string>();
  const obstacles = new Map<number, Set<string>>();
  const parts = array(d.parts, "asset.parts");
  if (d.editor_usage !== undefined)
    check(d.editor_usage === "map-background", "editor_usage", "unsupported asset capability");
  if (d.editor_usage === "map-background") {
    check(
      parts.length === 0 && d.states === undefined,
      "asset.parts",
      "map background cannot contain editable parts or states",
    );
    const components = array(d.components, "asset.components");
    check(
      components.length > 0 && components.every((component) => component?.source_node === "ground"),
      "asset.components",
      "map background requires ground-only components",
    );
  } else check(parts.length > 0, "asset.parts", "expected nonempty asset");
  for (const part of parts) {
    object(part, "asset part");
    text(part.node, "asset part.node");
    text(part.name, "asset part.name");
    const identity = obstaclePartIdentity(part.node);
    if (part.mission_profile !== undefined) {
      text(part.mission_profile, "asset part.mission_profile");
      check(
        /^mission-[a-zA-Z0-9_-]+$/.test(part.node) && part.source_obstacle === undefined,
        part.node,
        "mission parts cannot claim an obstacle index",
      );
    } else {
      check(
        componentIdentityMatches(part.node, part.source_obstacle, part.source_components),
        part.node,
        "canonical obstacle mismatch",
      );
      const claims = obstacles.get(part.source_obstacle) ?? new Set<string>();
      const claim = identity!.component ?? "*";
      check(
        !claims.has(claim) && !claims.has("*") && !(claim === "*" && claims.size),
        part.node,
        "duplicate asset part",
      );
      claims.add(claim);
      obstacles.set(part.source_obstacle, claims);
    }
    check(!nodes.has(part.node), part.node, "duplicate asset part");
    nodes.add(part.node);
    if (part.default_hidden !== undefined)
      check(typeof part.default_hidden === "boolean", part.node, "invalid default_hidden");
    obstacle(part.obstacle_local_game, part.node);
    check(
      part.obstacle_local_game.points.length >= 3,
      part.node,
      "editable obstacle needs three points",
    );
  }
  if (d.states !== undefined)
    validateAssetStates(
      d.states,
      new Map(parts.map((part) => [part.node, !!part.default_hidden])),
      "asset.states",
    );
  check(
    d.state_variants === undefined || d.standalone_variants === undefined,
    "asset.variants",
    "cannot combine replacement and additional static variants",
  );
  for (const field of ["state_variants", "standalone_variants"])
    if (d[field] !== undefined) {
      check(
        d.states === undefined && d.editor_usage !== "map-background",
        "asset." + field,
        "static models cannot also define part states or map backgrounds",
      );
      const variants = object(d[field], "asset." + field);
      check(Object.keys(variants).length > 0, "asset.state_variants", "expected nonempty variants");
      for (const [key, value] of Object.entries(variants)) {
        check(
          key === "initial" || key === "applied",
          "asset.state_variants",
          "invalid static variant",
        );
        const variant = object(value, `asset.state_variants.${key}`);
        text(variant.name, "variant.name");
        if (variant.model_scene !== undefined)
          check(
            typeof variant.model_scene === "string" && !!variant.model_scene.trim(),
            "variant.model_scene",
            "expected nonempty scene name",
          );
        check(safeLibraryPath(variant.model), "variant.model", "expected safe relative path");
        if (variant.parts !== undefined)
          parseProjectionAssetDescriptor({
            ...d,
            state_variants: undefined,
            standalone_variants: undefined,
            model: variant.model,
            parts: variant.parts,
          });
      }
    }
  return value as ProjectionAssetDescriptor;
}

/** Validate exclusive endpoints against their owning parts and relative visibility. */
export function validateAssetStates(
  value: unknown,
  hidden: Map<string, boolean>,
  path: string,
): void {
  const states = object(value, path);
  check(states.active === "initial" || states.active === "applied", path, "invalid active state");
  const seen = new Set<string>();
  for (const endpoint of ["initial", "applied"]) {
    const members = array(states[endpoint], `${path}.${endpoint}`);
    check(members.length > 0, path, "state endpoint must be nonempty");
    for (const id of members) {
      text(id, path);
      check(hidden.has(id), path, `state member ${id} is outside its group`);
      check(!seen.has(id), path, `duplicate state member ${id}`);
      seen.add(id);
      check(
        hidden.get(id) === (states.active !== endpoint),
        path,
        `state visibility mismatch for ${id}`,
      );
    }
  }
}
