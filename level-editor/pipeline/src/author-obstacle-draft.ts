import { Document, NodeIO } from "@gltf-transform/core";
import earcut from "earcut";
import { gameToScene, type MapCamera, type Vec3 } from "../../shared/src/scene.ts";
import type { SightObstacle } from "../../shared/src/level.ts";
import type { Level3DObject } from "../../shared/src/level3d.ts";
import {
  validateAssetGameplay,
  type GameplayAssetDescriptor,
} from "../../shared/src/asset-gameplay.ts";

/** Author an independent physical asset draft; the volume mesh is not a finished appearance. */
export async function authorObstacleDraft(
  shape: SightObstacle,
  options: {
    id: string;
    name: string;
    map: string;
    sourceIndex: number;
    origin: Vec3;
    camera: MapCamera;
    visualPoles?: { bottom: Vec3; top: Vec3; radius: number }[];
  },
) {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(options.id) || !options.name.trim())
    throw new Error("Obstacle draft needs a stable ID and name");
  if (
    !Number.isInteger(options.sourceIndex) ||
    options.sourceIndex < 0 ||
    options.origin.length !== 3 ||
    !options.origin.every(Number.isFinite)
  )
    throw new Error("Invalid obstacle draft source or origin");
  if (shape.projection_area != null || shape.material_indices?.length)
    throw new Error("Receiving surfaces and material regions require separate authoring");
  if (
    shape.points.length < 3 ||
    shape.points.some(
      (p) => ![p.x, p.y, p.z_bottom, p.z_top].every(Number.isFinite) || p.z_bottom > p.z_top,
    )
  )
    throw new Error("Obstacle draft needs finite, ordered volume vertices");
  const local: SightObstacle = structuredClone(shape);
  delete local.projection_area;
  delete local.projection_plane;
  local.material_indices = [];
  local.points = shape.points.map((p) => ({
    x: p.x - options.origin[0],
    y: p.y - options.origin[1],
    z_bottom: p.z_bottom - options.origin[2],
    z_top: p.z_top - options.origin[2],
  }));
  const node = `building-${String(options.sourceIndex).padStart(3, "0")}`;
  const descriptor: GameplayAssetDescriptor = {
    version: 1,
    kind: "projection-mapped-asset",
    id: options.id,
    name: options.name,
    source_map: options.map,
    source_origin_scene: gameToScene(options.camera, ...options.origin),
    asset_type: "Unfinished physical asset",
    tags: ["draft", "appearance-incomplete"],
    model: "model.glb",
    model_scene: "default",
    resources: [],
    parts: [
      {
        node,
        name: options.name,
        source_obstacle: options.sourceIndex,
        obstacle_local_game: local,
      },
    ],
    gameplay: { version: 1, collision: "parts", surfaces: [], doors: [] },
  };
  validateAssetGameplay(descriptor.gameplay!, descriptor);
  const model = new Document(),
    buffer = model.createBuffer();
  const positions = ["z_bottom", "z_top"].flatMap((height) =>
    local.points.flatMap((p) =>
      gameToScene(options.camera, p.x, p.y, height === "z_bottom" ? p.z_bottom : p.z_top),
    ),
  );
  const count = local.points.length;
  const cap = earcut(local.points.flatMap((p) => [p.x, p.y]));
  if (!cap.length) throw new Error("Obstacle draft has no triangulable footprint");
  const indices: number[] = [];
  for (let i = 0; i < cap.length; i += 3) {
    indices.push(cap[i]!, cap[i + 1]!, cap[i + 2]!);
    indices.push(cap[i + 2]! + count, cap[i + 1]! + count, cap[i]! + count);
  }
  for (let i = 0; i < count; i++) {
    const j = (i + 1) % count;
    indices.push(i, j, j + count, i, j + count, i + count);
  }
  const material = model
    .createMaterial("Unfinished volume preview")
    .setBaseColorFactor([0.55, 0.45, 0.3, 1])
    .setDoubleSided(true);
  const primitive = model
    .createPrimitive()
    .setMaterial(material)
    .setAttribute(
      "POSITION",
      model
        .createAccessor()
        .setType("VEC3")
        .setBuffer(buffer)
        .setArray(new Float32Array(positions)),
    )
    .setIndices(
      model.createAccessor().setType("SCALAR").setBuffer(buffer).setArray(new Uint32Array(indices)),
    );
  const frame = model
    .createNode(node)
    .setMesh(model.createMesh(options.name).addPrimitive(primitive));
  for (const [index, pole] of (options.visualPoles ?? []).entries()) {
    if (
      pole.bottom.length !== 3 ||
      pole.top.length !== 3 ||
      ![...pole.bottom, ...pole.top, pole.radius].every(Number.isFinite) ||
      pole.radius <= 0 ||
      pole.top[2] <= pole.bottom[2]
    )
      throw new Error("Visual pole needs finite endpoints, positive radius and increasing height");
    const vertices = [pole.bottom, pole.top].flatMap(([x, y, z]) =>
      Array.from({ length: 8 }, (_, i) => {
        const angle = (i * Math.PI) / 4;
        return gameToScene(
          options.camera,
          x - options.origin[0] + pole.radius * Math.cos(angle),
          y - options.origin[1] + pole.radius * Math.sin(angle),
          z - options.origin[2],
        );
      }).flat(),
    );
    const triangles: number[] = [];
    for (let i = 0; i < 8; i++) {
      const j = (i + 1) % 8;
      triangles.push(i, j, j + 8, i, j + 8, i + 8);
    }
    for (let i = 1; i < 7; i++) triangles.push(0, i + 1, i, 8, i + 8, i + 9);
    const timber = model
      .createPrimitive()
      .setMaterial(material)
      .setAttribute(
        "POSITION",
        model
          .createAccessor()
          .setType("VEC3")
          .setBuffer(buffer)
          .setArray(new Float32Array(vertices)),
      )
      .setIndices(
        model
          .createAccessor()
          .setType("SCALAR")
          .setBuffer(buffer)
          .setArray(new Uint32Array(triangles)),
      );
    frame.addChild(
      model
        .createNode(`visual-pole-${index + 1}`)
        .setMesh(model.createMesh("Reviewed support pole").addPrimitive(timber)),
    );
  }
  const wrapper = model.createNode("map").setRotation([-Math.SQRT1_2, 0, 0, Math.SQRT1_2]);
  wrapper.addChild(
    model.createNode(options.id).setExtras({ asset_group: options.id }).addChild(frame),
  );
  model.getRoot().setDefaultScene(model.createScene("default").addChild(wrapper));
  const placement: Level3DObject = {
    id: options.id,
    node: `asset:${options.id}:${node}`,
    name: options.name,
    kind: "building",
    source: { map: options.map, obstacle: options.sourceIndex },
    obstacle: structuredClone(local),
    transform: { dx: options.origin[0], dy: options.origin[1], dz: options.origin[2], rot_deg: 0 },
  };
  return {
    descriptor,
    placement,
    model: await new NodeIO().writeBinary(model),
    review: { status: "needs-review", appearanceComplete: false, masksComplete: false },
  };
}
