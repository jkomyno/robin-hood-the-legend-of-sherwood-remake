/** One-time authoring of a physical owner independently of shared visual provenance. */
import fs from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import { gameToScene, sceneToGame, partMatrix, type Vec3 } from "@rle/shared";
import type { ProtoLevel } from "../../shared/src/level.ts";
import { readStoredMap, pinnedDescriptors } from "./stored-map.ts";
import { sha256 } from "./bundle-asset-states.ts";

const { values } = parseArgs({
  options: Object.fromEntries(
    ["source", "recipe", "map", "library", "out"].map((key) => [key, { type: "string" as const }]),
  ),
});
if (!values.source || !values.recipe || !values.map || !values.library || !values.out)
  throw new Error(
    "Usage: --source LEVEL_JSON --recipe REVIEWED_JSON --map SCENE --library LIBRARY --out NEW_DIRECTORY",
  );
const bytes = await fs.readFile(values.source);
const proto: ProtoLevel = JSON.parse(bytes.toString());
const recipe: {
  source_sha256: string;
  obstacle: number;
  review: string;
  owner: string;
  node: string;
  parts: { asset: string; nodes: string[]; model_sha256: string; descriptor_sha256: string }[];
} = JSON.parse(await fs.readFile(values.recipe, "utf8"));
const source = proto.sight_obstacles[recipe.obstacle];
if (sha256(bytes) !== recipe.source_sha256 || !recipe.review.trim() || !source)
  throw new Error("Owned volume source or review missing/changed");
if (
  source.projection_area != null ||
  source.projection_plane ||
  source.material_indices.length ||
  proto.masks.some((m) => m.obstacle_indices.includes(recipe.obstacle)) ||
  proto.patches.some((p) =>
    [...p.old_sight_obstacles, ...p.new_sight_obstacles].includes(recipe.obstacle),
  )
)
  throw new Error("Linked or receiving volumes need separate ownership migration");
const document = await readStoredMap(values.map, values.library);
const descriptors = await pinnedDescriptors(
  values.library,
  document.assetSources ?? [],
  document.sceneAssets,
);
const owners = document.objects.filter((p) => p.source.obstacle === recipe.obstacle);
const claims = recipe.parts.flatMap((p) => p.nodes.map((node) => `asset:${p.asset}:${node}`));
if (
  new Set(claims).size !== claims.length ||
  claims.length !== owners.length ||
  owners.some((p) => !claims.includes(p.node)) ||
  !claims.includes(`asset:${recipe.owner}:${recipe.node}`)
)
  throw new Error("Owned volume recipe must review every visual component exactly once");
const outputs = new Map<string, string>();
for (const entry of recipe.parts) {
  const reference = document.assetSources?.find((s) => s.id === entry.asset);
  const descriptor = descriptors.get(entry.asset);
  if (
    !reference ||
    !descriptor ||
    reference.model_sha256 !== entry.model_sha256 ||
    reference.descriptor_sha256 !== entry.descriptor_sha256 ||
    sha256(await fs.readFile(path.join(values.library, reference.model))) !== entry.model_sha256
  )
    throw new Error(`Owned volume input changed or already published: ${entry.asset}`);
  const authored = JSON.parse(
    await fs.readFile(path.join(values.library, reference.descriptor), "utf8"),
  );
  if (authored.gameplay)
    throw new Error(`Owned volume needs explicit published gameplay migration: ${entry.asset}`);
  for (const node of entry.nodes) {
    const part = descriptor.parts.find((p) => p.node === node);
    if (
      !part?.obstacle_local_game ||
      part.source_obstacle !== recipe.obstacle ||
      part.mission_profile
    )
      throw new Error(`Owned volume component changed: ${entry.asset}/${node}`);
    delete part.sight_join_caps;
    delete part.sight_join_edges;
    if (entry.asset !== recipe.owner || node !== recipe.node) {
      part.collision = "none";
      continue;
    }
    delete part.collision;
    const object = owners.find((p) => p.node === `asset:${entry.asset}:${node}`)!;
    const matrix = partMatrix(document.camera, document, object);
    const localize = (point: Vec3): Vec3 => {
      const scene = gameToScene(document.camera, ...point);
      const offset = scene.map((v, j) => v - matrix[12 + j]!) as Vec3;
      return sceneToGame(
        document.camera,
        [0, 1, 2].map(
          (col) =>
            matrix[col * 4]! * offset[0] +
            matrix[col * 4 + 1]! * offset[1] +
            matrix[col * 4 + 2]! * offset[2],
        ) as Vec3,
      );
    };
    part.obstacle_local_game = {
      ...structuredClone(source),
      points: source.points.map((p) => {
        const bottom = localize([p.x, p.y, p.z_bottom]),
          top = localize([p.x, p.y, p.z_top]);
        if (Math.hypot(bottom[0] - top[0], bottom[1] - top[1]) > 1e-5)
          throw new Error("Owned volume needs a vertical asset frame");
        return { x: top[0], y: top[1], z_bottom: bottom[2], z_top: top[2] };
      }),
    };
  }
  outputs.set(entry.asset, JSON.stringify({ ...authored, ...descriptor }, null, 2) + "\n");
}
await fs.mkdir(values.out);
for (const [id, bytes] of outputs) {
  await fs.mkdir(path.join(values.out, encodeURIComponent(id)));
  await fs.writeFile(path.join(values.out, encodeURIComponent(id), "asset.json"), bytes);
}
await fs.writeFile(
  path.join(values.out, "partition-review.json"),
  JSON.stringify(
    {
      ...recipe,
      status: "needs-review",
      descriptors: [...outputs].map(([id, bytes]) => ({
        id,
        path: encodeURIComponent(id) + "/asset.json",
        sha256: sha256(bytes),
      })),
    },
    null,
    2,
  ),
);
console.log(
  JSON.stringify({
    assets: outputs.size,
    physicalOwner: recipe.owner,
    visualComponents: claims.length - 1,
    out: values.out,
  }),
);
