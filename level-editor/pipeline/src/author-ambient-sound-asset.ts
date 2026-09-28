import { Document, NodeIO } from "@gltf-transform/core";
import type { SoundSource } from "../../shared/src/level.ts";
import type { Vec3 } from "../../shared/src/scene.ts";
import type { Level3DObject } from "../../shared/src/level3d.ts";
import {
  validateAssetGameplay,
  type GameplayAssetDescriptor,
} from "../../shared/src/asset-gameplay.ts";
import { recoverSoundSource } from "./recover-sound-source.ts";

/** Explicit authoring of a standalone acoustic region, independent of visual buildings. */
export async function authorAmbientSoundAsset(
  sound: SoundSource,
  options: { id: string; name: string; map: string; origin: Vec3 },
) {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(options.id) || !options.name.trim())
    throw new Error("Ambient asset needs a stable ID and name");
  if (options.origin.length !== 3 || !options.origin.every(Number.isFinite))
    throw new Error("Ambient asset origin must be finite");
  if (sound.global) throw new Error("Global ambience belongs to terrain metadata");
  const node = "scenery-emitter";
  const descriptor: GameplayAssetDescriptor = {
    version: 1,
    kind: "projection-mapped-asset",
    id: options.id,
    name: options.name,
    source_map: options.map,
    asset_type: "Sound region",
    tags: ["ambient", "gameplay"],
    model: "model.glb",
    model_scene: "default",
    resources: [],
    parts: [{ node, name: options.name, scenery: true, gameplay_only: true }],
    gameplay: {
      version: 1,
      collision: "none",
      surfaces: [],
      doors: [],
      sounds: [
        recoverSoundSource(sound, "ambient", node, ([x, y, z]) => [
          x - options.origin[0],
          y - options.origin[1],
          z - options.origin[2],
        ]),
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
