/** One-time authoring of explicitly reviewed missing objects; not a compiler fallback. */
import fs from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import type { ProtoLevel } from "../../shared/src/level.ts";
import type { Vec3 } from "../../shared/src/scene.ts";
import { sha256 } from "./bundle-asset-states.ts";
import { authorObstacleDraft } from "./author-obstacle-draft.ts";

const { values } = parseArgs({
  options: { source: { type: "string" }, recipe: { type: "string" }, out: { type: "string" } },
});
if (!values.source || !values.recipe || !values.out)
  throw new Error("Usage: --source LEVEL_JSON --recipe REVIEWED_JSON --out NEW_DIRECTORY");
const source = await fs.readFile(values.source);
const proto: ProtoLevel = JSON.parse(source.toString());
const recipe: {
  map: string;
  source_sha256: string;
  entries: {
    source: number;
    id: string;
    name: string;
    origin: Vec3;
    review: string;
    visualPoles?: { bottom: Vec3; top: Vec3; radius: number }[];
  }[];
} = JSON.parse(await fs.readFile(values.recipe, "utf8"));
if (recipe.source_sha256 !== sha256(source)) throw new Error("Obstacle authoring source changed");
if (!recipe.entries.length) throw new Error("Obstacle draft recipe is empty");
const ids = new Set<string>(),
  indices = new Set<number>();
const outputs = [];
for (const entry of recipe.entries) {
  const shape = proto.sight_obstacles[entry.source];
  if (
    !Number.isInteger(entry.source) ||
    !shape ||
    ids.has(entry.id) ||
    indices.has(entry.source) ||
    !entry.review.trim()
  )
    throw new Error("Invalid, unreviewed or duplicate obstacle draft");
  if (
    proto.patches.some((p) =>
      [...p.old_sight_obstacles, ...p.new_sight_obstacles].includes(entry.source),
    )
  )
    throw new Error("Changing geometry needs its complete asset state assembly");
  ids.add(entry.id);
  indices.add(entry.source);
  outputs.push(
    await authorObstacleDraft(shape, {
      ...entry,
      sourceIndex: entry.source,
      map: recipe.map,
      camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    }),
  );
}
await fs.mkdir(values.out);
const assetSources = [],
  objects = [];
for (const asset of outputs) {
  const dir = `3d-assets/${asset.descriptor.id}`;
  await fs.mkdir(path.join(values.out, dir), { recursive: true });
  const descriptor = JSON.stringify(asset.descriptor, null, 2) + "\n";
  await fs.writeFile(path.join(values.out, dir, "asset.json"), descriptor);
  await fs.writeFile(path.join(values.out, dir, "model.glb"), asset.model);
  await fs.writeFile(
    path.join(values.out, dir, "review.json"),
    JSON.stringify(asset.review, null, 2) + "\n",
  );
  assetSources.push({
    id: asset.descriptor.id,
    descriptor: `${dir}/asset.json`,
    descriptor_sha256: sha256(descriptor),
    model: `${dir}/model.glb`,
    model_sha256: sha256(asset.model),
    model_scene: "default",
    resources: [],
  });
  objects.push(asset.placement);
}
await fs.writeFile(
  path.join(values.out, "obstacle-draft-assets.json"),
  JSON.stringify(
    {
      status: "needs-review",
      scope: "physical-volume-drafts-not-complete-visual-assets",
      assetSources,
      objects,
    },
    null,
    2,
  ) + "\n",
);
console.log(JSON.stringify({ assets: outputs.length, out: values.out, status: "needs-review" }));
