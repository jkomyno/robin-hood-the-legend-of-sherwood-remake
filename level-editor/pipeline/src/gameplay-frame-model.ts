import { Document, NodeIO } from "@gltf-transform/core";

/** Invisible standalone asset with the same frame hierarchy used by visual assets. */
export async function gameplayFrameModel(asset: string, part: string): Promise<Uint8Array> {
  const model = new Document();
  const frame = model.createNode(part).setExtras({ scenery: true, gameplay_only: true });
  const group = model.createNode(asset).setExtras({ asset_group: asset }).addChild(frame);
  const map = model
    .createNode("map")
    .setRotation([-Math.SQRT1_2, 0, 0, Math.SQRT1_2])
    .addChild(group);
  const scene = model.createScene("default").addChild(map);
  model.getRoot().setDefaultScene(scene);
  return new NodeIO().writeBinary(model);
}
