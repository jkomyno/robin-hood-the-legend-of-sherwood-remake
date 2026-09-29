import { Document, NodeIO } from "@gltf-transform/core";
import type { LightSector, MotionArea, SightObstacle } from "../../shared/src/level.ts";
import type { Vec3 } from "../../shared/src/scene.ts";
import type { Level3DObject } from "../../shared/src/level3d.ts";
import {
  validateAssetGameplay,
  type GameplayAssetDescriptor,
} from "../../shared/src/asset-gameplay.ts";
import { recoverLightField } from "./recover-light-region.ts";

/** Author an independently placed environmental lighting field in local coordinates. */
export async function authorLightRegionAsset(
  light: LightSector,
  obstacles: SightObstacle[],
  motionAreas: MotionArea[],
  options: { id: string; name: string; map: string; origin: Vec3; motionSectors?: number[] },
) {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(options.id) || !options.name.trim())
    throw new Error("Light asset needs a stable ID and name");
  if (options.origin.length !== 3 || !options.origin.every(Number.isFinite))
    throw new Error("Light asset origin must be finite");
  const node = "scenery-light";
  const { region } = recoverLightField(
    light,
    "environment",
    obstacles,
    motionAreas,
    options.motionSectors,
  );
  const localize = ([x, y, z]: Vec3): Vec3 => [
    x - options.origin[0],
    y - options.origin[1],
    z - options.origin[2],
  ];
  const descriptor: GameplayAssetDescriptor = {
    version: 1,
    kind: "projection-mapped-asset",
    id: options.id,
    name: options.name,
    source_map: options.map,
    asset_type: "Light region",
    tags: ["lighting", "gameplay"],
    model: "model.glb",
    model_scene: "default",
    resources: [],
    parts: [{ node, name: options.name, scenery: true, gameplay_only: true }],
    gameplay: {
      version: 1,
      collision: "none",
      surfaces: [],
      doors: [],
      lights: [
        {
          ...region,
          node,
          polygon: region.polygon.map(localize),
          ...(region.receivers ? { receivers: region.receivers.map(localize) } : {}),
        },
      ],
    },
  };
  validateAssetGameplay(descriptor.gameplay, descriptor);
  const model = new Document();
  const scene = model.createScene("default").addChild(model.createNode(node));
  model.getRoot().setDefaultScene(scene);
  const placement: Level3DObject = {
    id: options.id,
    name: options.name,
    kind: "scenery",
    node: `asset:${options.id}:${node}`,
    source: { map: options.map },
    transform: { dx: options.origin[0], dy: options.origin[1], dz: options.origin[2], rot_deg: 0 },
  };
  return { descriptor, model: await new NodeIO().writeBinary(model), placement };
}
