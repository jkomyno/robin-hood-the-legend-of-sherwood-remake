import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { parseArgs } from "node:util";
import type { ProtoLevel } from "../../shared/src/level.ts";
import type { Vec3 } from "../../shared/src/scene.ts";
import type { ExternalAssetSource } from "../../shared/src/projection-assets.ts";
import type { Level3DObject } from "../../shared/src/level3d.ts";
import { authorAmbientSoundAsset } from "./author-ambient-sound-asset.ts";

const { values } = parseArgs({
  options: {
    source: { type: "string" },
    recipe: { type: "string" },
    map: { type: "string" },
    out: { type: "string" },
  },
});
if (!values.source || !values.recipe || !values.map || !values.out)
  throw new Error(
    "Usage: --source <level.json> --recipe <reviewed.json> --map <name> --out <library-root>",
  );
const hash = (bytes: Uint8Array | string) => createHash("sha256").update(bytes).digest("hex");
const bytes = await fs.readFile(values.source);
const proto: ProtoLevel = JSON.parse(bytes.toString("utf8"));
const recipe: {
  source_sha256: string;
  entries: { source: number; id: string; name: string; origin: Vec3 }[];
} = JSON.parse(await fs.readFile(values.recipe, "utf8"));
if (recipe.source_sha256 !== hash(bytes)) throw new Error("Ambient authoring source changed");
const indices = new Set<number>(),
  ids = new Set<string>();
const assets = [];
for (const entry of recipe.entries) {
  if (
    !Number.isInteger(entry.source) ||
    entry.source < 0 ||
    !proto.sound_sources[entry.source] ||
    indices.has(entry.source) ||
    ids.has(entry.id)
  )
    throw new Error("Invalid or duplicate ambient source/asset");
  indices.add(entry.source);
  ids.add(entry.id);
  assets.push(
    await authorAmbientSoundAsset(proto.sound_sources[entry.source]!, {
      ...entry,
      map: values.map,
    }),
  );
}
if (!assets.length) throw new Error("Ambient recipe has no assets");
const assetSources: ExternalAssetSource[] = [],
  objects: Level3DObject[] = [];
for (const asset of assets) {
  const root = `3d-assets/${asset.descriptor.id}`;
  const descriptor = JSON.stringify(asset.descriptor, null, 2) + "\n";
  await fs.mkdir(path.join(values.out, root), { recursive: true });
  await fs.writeFile(path.join(values.out, root, "asset.json"), descriptor);
  await fs.writeFile(path.join(values.out, root, "model.glb"), asset.model);
  // Empty gameplay-frame models are already minimal; the runtime derivative is identical.
  await fs.writeFile(path.join(values.out, root, "lossy.glb"), asset.model);
  await fs.writeFile(
    path.join(values.out, root, "lossy.glb.receipt.json"),
    JSON.stringify({
      source: hash(asset.model),
      output: hash(asset.model),
      producer: "author-ambient-sound-assets",
      mode: "identity-gameplay-frame",
      version: 1,
    }) + "\n",
  );
  assetSources.push({
    id: asset.descriptor.id,
    descriptor: `${root}/asset.json`,
    model: `${root}/model.glb`,
    descriptor_sha256: hash(descriptor),
    model_sha256: hash(asset.model),
    model_scene: "default",
    resources: [],
  });
  objects.push(asset.placement);
}
await fs.writeFile(
  path.join(values.out, "ambient-sound-assets.json"),
  JSON.stringify({ assetSources, objects }, null, 2) + "\n",
);
console.log(JSON.stringify({ assets: assets.length, out: values.out }));
