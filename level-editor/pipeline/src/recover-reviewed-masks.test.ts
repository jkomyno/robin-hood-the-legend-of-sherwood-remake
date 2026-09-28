import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { Document, NodeIO } from "@gltf-transform/core";
import { maskAssetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { gameToScene } from "../../shared/src/scene.ts";
import { sceneToGltf } from "../../shared/src/geometry.ts";
import { recoverReviewedMasks, type ReviewedMaskRecipe } from "./recover-reviewed-masks.ts";

test("reviewed static-mask migration verifies model, receiving anchor and state ownership", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "reviewed-masks-"));
  try {
    const { document, assets, hut } = maskAssetCompilerFixture();
    const authored = hut.gameplay!.masks![0]!;
    const model = new Document(),
      buffer = model.createBuffer();
    const positions = authored.triangles
      .flat()
      .flatMap((p) => sceneToGltf(gameToScene(document.camera, ...p)));
    const primitive = model
      .createPrimitive()
      .setAttribute(
        "POSITION",
        model
          .createAccessor()
          .setBuffer(buffer)
          .setType("VEC3")
          .setArray(new Float32Array(positions)),
      );
    const scene = model
      .createScene("default")
      .addChild(
        model.createNode(authored.node).setMesh(model.createMesh().addPrimitive(primitive)),
      );
    model.getRoot().setDefaultScene(scene);
    const bytes = await new NodeIO().writeBinary(model);
    const hash = createHash("sha256").update(bytes).digest("hex");
    await fs.writeFile(path.join(root, "model.glb"), bytes);
    const reference = document.assetSources!.find((a) => a.id === hut.id)!;
    Object.assign(reference, {
      model: "model.glb",
      model_sha256: hash,
      model_scene: "default",
      resources: [],
    });
    // This fixture has no pinned descriptor file; the model itself is pinned.
    const descriptorBytes = Buffer.from("{}");
    await fs.writeFile(path.join(root, "asset.json"), descriptorBytes);
    reference.descriptor = "asset.json";
    reference.descriptor_sha256 = createHash("sha256").update(descriptorBytes).digest("hex");
    document.objects.find((p) => p.node === `asset:${hut.id}:${authored.node}`)!.source.obstacle =
      0;
    const geometry = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
    const proto = {
      masks: geometry.masks!,
      sight_obstacles: geometry.sight_obstacles,
      motion_data: geometry.motion_data,
      patches: [],
    };
    const recipe: ReviewedMaskRecipe = {
      asset: hut.id,
      model_sha256: hash,
      entries: [
        {
          source: 0,
          id: authored.id,
          node: authored.node,
          anchor: [345, 345, 0],
          characterHeights: [0, 0],
        },
      ],
    };
    const recovered = await recoverReviewedMasks(root, document, proto, [recipe]);
    assert.equal(recovered.length, 1);
    hut.gameplay!.masks![0] = recovered[0]!.definition;
    assert.deepEqual(
      compileAssetGameplay(document, assets, [0, 0, 2000, 2000]).masks![0],
      geometry.masks![0],
    );
    await assert.rejects(
      recoverReviewedMasks(root, document, proto, [{ ...recipe, model_sha256: "changed" }]),
      /model changed/,
    );
    await assert.rejects(
      recoverReviewedMasks(root, document, proto, [
        { ...recipe, entries: [{ ...recipe.entries[0]!, anchor: [-100, -100, 0] }] },
      ]),
      /receiving layer/,
    );
    await assert.rejects(
      recoverReviewedMasks(root, document, proto, [
        { ...recipe, entries: [{ ...recipe.entries[0]!, anchor: [345, 346, 1] }] },
      ]),
      /receiving elevation/,
    );
    await assert.rejects(
      recoverReviewedMasks(
        root,
        document,
        { ...proto, patches: [{ old_masks: [{ layer: 0, index: 0 }], new_masks: [] }] },
        [recipe],
      ),
      /requires state recovery/,
    );
    const duplicate = structuredClone(
      document.objects.find((p) => p.node === `asset:${hut.id}:${authored.node}`)!,
    );
    duplicate.id += "-copy";
    duplicate.transform.dx += 500;
    // A copy without an obstacle binding must still not supply migration geometry.
    duplicate.source = { map: document.map };
    await assert.rejects(
      recoverReviewedMasks(
        root,
        { ...document, objects: [...document.objects, duplicate] },
        proto,
        [recipe],
      ),
      /needs one placement/,
    );
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
