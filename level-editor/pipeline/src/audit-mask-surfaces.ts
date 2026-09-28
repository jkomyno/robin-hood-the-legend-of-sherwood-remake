/** Offline geometry-support audit for an explicitly selected asset and masks. */
import fs from "node:fs/promises";
import { createHash } from "node:crypto";
import { parseArgs } from "node:util";
import type { ProtoLevel } from "../../shared/src/level.ts";
import { maskReferenceResolver } from "../../shared/src/mask-references.ts";
import { partMatrix } from "../../shared/src/level3d.ts";
import { applyAffineMatrix, gltfToScene, sceneToGame } from "../../shared/src/geometry.ts";
import { rasterizeMaskGeometry } from "../../shared/src/compile-mask-geometry.ts";
import { readStoredMap } from "./stored-map.ts";
import { loadSceneModel } from "./scene-assets.ts";
import { maskRecoveryMesh, maskRecoveryTextures } from "./mask-recovery-mesh.ts";
import { maskSurfaceCoverage } from "./mask-surface-coverage.ts";

const { values } = parseArgs({
  options: {
    library: { type: "string" },
    map: { type: "string" },
    source: { type: "string" },
    asset: { type: "string" },
    masks: { type: "string" },
    out: { type: "string" },
  },
});
if (
  !values.library ||
  !values.map ||
  !values.source ||
  !values.asset ||
  !values.masks ||
  !values.out
)
  throw new Error(
    "Usage: --library <dir> --map <scene> --source <level> --asset <id> --masks <comma-separated indices> --out <report>",
  );
const indices = values.masks.split(",").map((s) => {
  if (!/^\d+$/.test(s)) throw new Error(`Invalid mask index: ${s}`);
  return Number(s);
});
if (new Set(indices).size !== indices.length) throw new Error("Duplicate mask index");
const bytes = await fs.readFile(values.source);
const proto: ProtoLevel = JSON.parse(bytes.toString("utf8"));
for (const index of indices) if (!proto.masks[index]) throw new Error(`Missing mask ${index}`);
const document = await readStoredMap(values.map, values.library);
const reference = document.assetSources?.find((a) => a.id === values.asset);
if (!reference) throw new Error(`Missing asset ${values.asset}`);
const prefix = `asset:${reference.id}:`;
const parts = document.objects.filter((p) => p.node.startsWith(prefix));
if (new Set(parts.map((p) => p.node)).size !== parts.length)
  throw new Error("Audit needs one placement of the selected asset");
const model = await loadSceneModel(values.library, {
  ...reference,
  role: "objects",
  resources: reference.resources ?? [],
});
const textures = await maskRecoveryTextures(model);
const surfaces = parts.flatMap((part) => {
  const matrix = partMatrix(document.camera, document, part);
  return maskRecoveryMesh(
    model,
    part.node.slice(prefix.length),
    (p) => sceneToGame(document.camera, applyAffineMatrix(matrix, gltfToScene(p))),
    textures,
  );
});
const tiles = surfaces.length ? rasterizeMaskGeometry(surfaces, proto.masks[indices[0]!]!) : [];
const results = indices.map((index) => ({
  index,
  ...maskSurfaceCoverage(proto.masks[index]!, tiles),
}));
const resolve = maskReferenceResolver(proto.masks);
const selected = new Set(indices);
const states = proto.patches.flatMap((patch, index) => {
  const initial = resolve(patch.old_masks),
    applied = resolve(patch.new_masks);
  const all = [...initial, ...applied];
  if (!all.some((i) => selected.has(i))) return [];
  const unselected = all.filter((i) => !selected.has(i));
  return [
    {
      index,
      initial,
      applied,
      unselected,
      fullPixelSupport:
        !unselected.length &&
        all.every((i) => results.find((r) => r.index === i)?.missingPixels === 0),
    },
  ];
});
const report = {
  scope: "pixel-support-only-not-ownership-or-gameplay-parity",
  source_sha256: createHash("sha256").update(bytes).digest("hex"),
  map: document.map,
  asset: reference.id,
  model_sha256: reference.model_sha256,
  scene_sha256: createHash("sha256").update(JSON.stringify(document)).digest("hex"),
  faces: surfaces.length,
  results,
  states,
};
await fs.writeFile(values.out, JSON.stringify(report, null, 2) + "\n");
console.log(
  JSON.stringify({
    masks: results.length,
    unsupported: results.filter((r) => r.missingPixels).length,
    states,
  }),
);
