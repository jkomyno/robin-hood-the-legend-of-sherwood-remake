/** Build lightweight browser-only GLBs for the shared asset library. */
import fs from "node:fs/promises";
import path from "node:path";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { meshopt, simplify, textureCompress } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptSimplifier } from "meshoptimizer";
import sharp from "sharp";

const root = path.resolve(process.argv[2] ?? "../library/3d-assets");
const indexPath = path.join(root, "index.json");
const index = JSON.parse(await fs.readFile(indexPath, "utf8")) as { version: number; assets: Array<Record<string, unknown>> };
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ "meshopt.encoder": MeshoptEncoder });
for (const entry of index.assets) {
  const id = String(entry.id), model = String(entry.model);
  const source = path.join(root, model), preview = path.join(root, id, "preview.glb");
  const document = await io.read(source);
  await document.transform(
    simplify({ simplifier: MeshoptSimplifier, ratio: 0.12, error: 0.015 }),
    meshopt({ encoder: MeshoptEncoder, level: "high" }),
    textureCompress({ encoder: sharp, targetFormat: "avif", resize: [256, 256], quality: 45 }),
  );
  await io.write(preview, document);
  entry.preview_model = `${id}/preview.glb`;
  const sourceBytes = (await fs.stat(source)).size, previewBytes = (await fs.stat(preview)).size;
  console.log(`${id}: ${(sourceBytes / 1048576).toFixed(1)} MB -> ${(previewBytes / 1048576).toFixed(1)} MB`);
}
await fs.writeFile(indexPath, JSON.stringify(index, null, 2) + "\n");
