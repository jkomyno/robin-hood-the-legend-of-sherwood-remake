/** One-time recovery of reviewed physical partitions into asset descriptors. */
import fs from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import { gameToScene, sceneToGame, partMatrix, type Vec3 } from "@rle/shared";
import type { ProtoLevel } from "../../shared/src/level.ts";
import { readStoredMap, pinnedDescriptors } from "./stored-map.ts";
import { sha256 } from "./bundle-asset-states.ts";
import { partitionFlatVolume, type VolumeVertex } from "./partition-flat-volume.ts";

const { values } = parseArgs({
  options: {
    source: { type: "string" },
    recipe: { type: "string" },
    map: { type: "string" },
    library: { type: "string" },
    out: { type: "string" },
  },
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
  parts: {
    asset: string;
    node: string;
    model_sha256: string;
    descriptor_sha256: string;
    vertices: VolumeVertex[];
    height_range?: [number, number];
  }[];
} = JSON.parse(await fs.readFile(values.recipe, "utf8"));
if (sha256(bytes) !== recipe.source_sha256 || !recipe.review.trim())
  throw new Error("Partition source or review missing/changed");
const source = proto.sight_obstacles[recipe.obstacle];
if (!Number.isInteger(recipe.obstacle) || !source) throw new Error("Invalid partition source");
if (
  proto.masks.some((m) => m.obstacle_indices.includes(recipe.obstacle)) ||
  proto.patches.some((p) =>
    [...p.old_sight_obstacles, ...p.new_sight_obstacles].includes(recipe.obstacle),
  )
)
  throw new Error("Linked masks and changing volumes need separate partition bindings");
const shapes = partitionFlatVolume(
  source,
  recipe.parts.map((p) => p.vertices),
  recipe.parts.some((p) => p.height_range)
    ? recipe.parts.map((p) => {
        if (!p.height_range) throw new Error("Every stacked partition requires a height range");
        return p.height_range;
      })
    : undefined,
);
const document = await readStoredMap(values.map, values.library);
const descriptors = await pinnedDescriptors(
  values.library,
  document.assetSources ?? [],
  document.sceneAssets,
);
const owners = document.objects.filter((p) => p.source.obstacle === recipe.obstacle);
if (
  owners.length !== recipe.parts.length ||
  new Set(recipe.parts.map((p) => p.asset + ":" + p.node)).size !== recipe.parts.length
)
  throw new Error("Partition recipe must assign every physical owner exactly once");
const outputs = new Map<string, string>();
for (const [i, entry] of recipe.parts.entries()) {
  const reference = document.assetSources?.find((s) => s.id === entry.asset);
  const descriptor = descriptors.get(entry.asset);
  const matches = owners.filter((p) => p.node === `asset:${entry.asset}:${entry.node}`);
  const part = descriptor?.parts.find((p) => p.node === entry.node);
  if (
    !reference ||
    !descriptor ||
    !part?.obstacle_local_game ||
    part.source_obstacle !== recipe.obstacle ||
    part.mission_profile ||
    matches.length !== 1 ||
    reference.model_sha256 !== entry.model_sha256 ||
    reference.descriptor_sha256 !== entry.descriptor_sha256 ||
    sha256(await fs.readFile(path.join(values.library, reference.model))) !== entry.model_sha256
  )
    throw new Error(`Partition ownership/model changed: ${entry.asset}`);
  const authored = JSON.parse(
    await fs.readFile(path.join(values.library, reference.descriptor), "utf8"),
  );
  if (authored.gameplay)
    throw new Error("Published gameplay needs explicit migration before replacing part geometry");
  const matrix = partMatrix(document.camera, document, matches[0]!);
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
  const shape = shapes[i]!;
  part.obstacle_local_game = {
    ...shape,
    points: shape.points.map((p) => {
      const bottom = localize([p.x, p.y, p.z_bottom]),
        top = localize([p.x, p.y, p.z_top]);
      if (Math.hypot(bottom[0] - top[0], bottom[1] - top[1]) > 1e-5)
        throw new Error("Partition needs a vertical asset frame");
      return { x: top[0], y: top[1], z_bottom: bottom[2], z_top: top[2] };
    }),
  };
  delete part.sight_join_caps;
  part.sight_join_edges = entry.height_range
    ? []
    : shape.points.flatMap((p, j): [Vec3, Vec3][] => {
        const q = shape.points[(j + 1) % shape.points.length]!;
        const matched = shapes.some(
          (other, k) =>
            k !== i &&
            other.points.some((a, n) => {
              const b = other.points[(n + 1) % other.points.length]!;
              return p.x === b.x && p.y === b.y && q.x === a.x && q.y === a.y;
            }),
        );
        return matched
          ? [[localize([p.x, p.y, p.z_bottom]), localize([q.x, q.y, q.z_bottom])]]
          : [];
      });
  if (entry.height_range) {
    part.sight_join_caps = [];
    if (entry.height_range[0] !== source.points[0]!.z_bottom) part.sight_join_caps.push("bottom");
    if (entry.height_range[1] !== source.points[0]!.z_top) part.sight_join_caps.push("top");
  }
  outputs.set(entry.asset, JSON.stringify({ ...authored, ...descriptor }, null, 2) + "\n");
}
await fs.mkdir(values.out);
for (const [id, descriptor] of outputs) {
  await fs.mkdir(path.join(values.out, encodeURIComponent(id)));
  await fs.writeFile(path.join(values.out, encodeURIComponent(id), "asset.json"), descriptor);
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
console.log(JSON.stringify({ assets: outputs.size, partitions: shapes.length, out: values.out }));
