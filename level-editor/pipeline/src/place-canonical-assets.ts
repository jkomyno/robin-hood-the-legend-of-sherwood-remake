/** Convert source placements to the same local catalog instances used by manual insertion. */
import fs from "node:fs/promises";
import path from "node:path";
import { mat4 } from "gl-matrix";
import {
  assetNodeKey,
  assetVariantId,
  serializeStoredMap,
  descriptorForSource,
  gameTransformMatrix,
  groupCentroid,
  groupParts,
  partPivot,
  partMatrix,
  transformedObstacle,
  parseLevel3D,
  patchBindingsFromMetadata,
  deriveAppearancePatches,
  assertPatchMappingEquivalent,
  modelPartPatchNodes,
  endpointPatchRule,
  type Level3D,
  type ProjectionAssetDescriptor,
  type ExternalAssetSource,
  type PatchBindings,
} from "@rle/shared";
import { transformAt } from "./refined-map-groups.ts";

const plan = JSON.parse(await fs.readFile(process.argv[2]!, "utf8"));
const descriptors = new Map<string, ProjectionAssetDescriptor>();
const models = new Map<string, any>();
async function partNodes(reference: ExternalAssetSource, root: string) {
  let model = models.get(reference.model);
  if (!model) {
    model = JSON.parse(await fs.readFile(path.join(plan.output, reference.model), "utf8"));
    models.set(reference.model, model);
  }
  const scene = reference.model_scene
    ? model.scenes.findIndex((item: { name?: string }) => item.name === reference.model_scene)
    : (model.scene ?? 0);
  if (scene < 0) throw new Error(`Missing asset scene ${reference.model_scene}`);
  return modelPartPatchNodes({ ...model, scene }, root);
}
async function descriptor(id: string) {
  if (!descriptors.has(id))
    descriptors.set(
      id,
      JSON.parse(await fs.readFile(path.join(plan.output, plan.references[id].descriptor), "utf8")),
    );
  return descriptors.get(id)!;
}
const report = [];
for (const item of plan.maps) {
  const old: Level3D = item.document,
    doc: Level3D = structuredClone(old);
  const references = new Map<string, ExternalAssetSource>();
  for (const ref of old.assetSources ?? []) {
    const id = ref.id.replace(/--state-(initial|applied)$/, "");
    const asset = await descriptor(id);
    const variant = ref.state_variant;
    references.set(ref.id, {
      ...plan.references[id],
      id: ref.id,
      model_scene: variant
        ? (asset.state_variants ?? asset.standalone_variants)![variant]!.model_scene
        : asset.model_scene,
      ...(variant ? { state_variant: variant } : {}),
    });
  }
  const origins = new Map<string, number[]>();
  const desired = new Map<string, mat4>();
  const reviewed: {
    part: Level3D["objects"][number];
    bindings: PatchBindings;
    nodes: Map<string, Record<string, unknown>>;
  }[] = [];
  const endpoints: {
    part: Level3D["objects"][number];
    patch: string;
    state: "initial" | "applied";
  }[] = [];
  for (const part of doc.objects) {
    const before = old.objects.find((p) => p.id === part.id)!;
    const external = before.node.startsWith("asset:");
    const oldRef = external
      ? old.assetSources!.find((r) => before.node.startsWith(`asset:${r.id}:`))!
      : undefined;
    const id = external
      ? oldRef!.id.replace(/--state-(initial|applied)$/, "")
      : item.owners[before.node];
    if (!id) throw new Error(`Missing owner: ${old.map}/${before.node}`);
    const asset = await descriptor(id);
    const node = external ? before.node.slice(`asset:${oldRef!.id}:`.length) : before.node;
    let variant = oldRef?.state_variant;
    let definition = (
      variant
        ? ((asset.state_variants ?? asset.standalone_variants)?.[variant]?.parts ?? asset.parts)
        : asset.parts
    ).find((p) => p.node === node);
    if (!definition) {
      variant = "applied";
      definition = (asset.state_variants ?? asset.standalone_variants)?.applied?.parts?.find(
        (p) => p.node === node,
      );
    }
    if (!definition) throw new Error(`Missing catalog part: ${id}/${node}`);
    const reference = {
      ...plan.references[id],
      id: variant ? assetVariantId(id, variant) : id,
      model_scene: variant
        ? (asset.state_variants ?? asset.standalone_variants)![variant]!.model_scene
        : asset.model_scene,
      ...(variant ? { state_variant: variant } : {}),
    };
    references.set(reference.id, reference);
    const origin: number[] = external ? [0, 0, 0] : plan.origins[id];
    if (!origin) throw new Error(`Missing origin: ${id}`);
    origins.set(part.id, origin);
    const translate = mat4.fromTranslation(new Float64Array(16), origin);
    desired.set(
      part.id,
      mat4.multiply(new Float64Array(16), partMatrix(old.camera, old, before), translate),
    );
    part.node = assetNodeKey(reference.id, node);
    if (definition.obstacle_local_game)
      part.obstacle = structuredClone(definition.obstacle_local_game);
    else delete part.obstacle;
    const bindings = patchBindingsFromMetadata(item.bindings[before.node]);
    if (bindings) {
      const nodes = await partNodes(reference, node);
      const placement = part.group ? doc.groups.find((group) => group.id === part.group)! : part;
      const mapping = ((placement.patches ??= {})[reference.id] ??= {});
      const root = bindings[node];
      const endpointState = reference.state_variant === "applied" ? "applied" : "initial";
      const endpointRule =
        root &&
        Object.keys(bindings).length === 1 &&
        Object.keys(root).length === 1 &&
        (endpointState === "initial" ? root.hide?.length === 1 : root.show?.length === 1) &&
        !nodes.get(node)?.[
          endpointState === "initial" ? "reveal_hide_when_applied" : "reveal_show_when_applied"
        ];
      if (endpointRule) {
        if (!part.group) throw new Error(`Static patch endpoint is not grouped: ${part.id}`);
        endpoints.push({
          part,
          patch: (endpointState === "initial" ? root.hide : root.show)![0]!,
          state: endpointState,
        });
      } else deriveAppearancePatches(bindings, nodes, mapping);
      reviewed.push({ part, bindings, nodes });
    }
  }
  for (const endpoint of endpoints) {
    const base = endpoint.part.node.split(":")[1]!.replace(/--state-applied$/, "");
    const mate = endpoints.find(
      (other) =>
        other !== endpoint &&
        other.part.group === endpoint.part.group &&
        other.part.node.split(":")[1]!.replace(/--state-applied$/, "") === base &&
        other.state !== endpoint.state &&
        other.patch === endpoint.patch,
    );
    if (!mate) throw new Error(`Unpaired static patch endpoint: ${endpoint.part.id}`);
    const group = doc.groups.find((item) => item.id === endpoint.part.group)!;
    (group.patches ??= {})[base] ??= {};
    const mapping = group.patches[base];
    if (mapping.state !== undefined && mapping.state !== endpoint.patch)
      throw new Error(`Conflicting endpoint patch: ${base}`);
    mapping.state = endpoint.patch;
  }
  const availableNodes = new Set<string>();
  for (const [id, asset] of descriptors) {
    for (const definition of asset.parts) availableNodes.add(`asset:${id}:${definition.node}`);
    for (const [state, variant] of Object.entries(asset.state_variants ?? {}))
      for (const definition of variant.parts ?? asset.parts)
        availableNodes.add(`asset:${id}--state-${state}:${definition.node}`);
  }
  for (const part of doc.objects) {
    const assetId = part.node.split(":")[1]!;
    const reference = references.get(assetId)!;
    const root = part.node.split(":").slice(2).join(":");
    const placement = part.group ? doc.groups.find((group) => group.id === part.group)! : part;
    const mapping = placement.patches?.[assetId] ?? {};
    const endpoint = endpointPatchRule(part.node, availableNodes, placement.patches);
    const reviewedPart = reviewed.find((item) => item.part === part);
    const nodes = reviewedPart?.nodes ?? (await partNodes(reference, root));
    assertPatchMappingEquivalent(reviewedPart?.bindings, nodes, mapping, root, endpoint);
  }
  for (const group of doc.groups) {
    const before = old.groups.find((g) => g.id === group.id)!;
    const members = groupParts(doc, group.id);
    const origin = members.length ? origins.get(members[0]!.id)! : [0, 0, 0];
    const matrix = mat4.multiply(
      new Float64Array(16),
      gameTransformMatrix(old.camera, before.transform, groupCentroid(groupParts(old, group.id))),
      mat4.fromTranslation(new Float64Array(16), origin),
    );
    group.transform = transformAt(doc, matrix, groupCentroid(members));
  }
  let maxError = 0;
  for (const part of doc.objects) {
    let local = desired.get(part.id)!;
    if (part.group) {
      const group = doc.groups.find((g) => g.id === part.group)!;
      const inverse = mat4.invert(
        new Float64Array(16),
        gameTransformMatrix(doc.camera, group.transform, groupCentroid(groupParts(doc, group.id))),
      );
      if (!inverse) throw new Error(`Singular placement: ${part.id}`);
      local = mat4.multiply(new Float64Array(16), inverse, local);
    }
    part.transform = transformAt(doc, local, partPivot(part));
  }
  for (const part of doc.objects) {
    if (part.kind === "scenery") {
      // No footprint to compare: check the placed matrix itself.
      const after = partMatrix(doc.camera, doc, part);
      const expected = desired.get(part.id)!;
      for (let i = 0; i < 16; i++)
        maxError = Math.max(maxError, Math.abs(after[i]! - expected[i]!));
      continue;
    }
    const before = transformedObstacle(
      old,
      old.objects.find((p) => p.id === part.id)!,
    );
    const after = transformedObstacle(doc, part);
    if (before.points.length !== after.points.length)
      throw new Error(`Footprint changed: ${old.map}/${part.id}`);
    for (let i = 0; i < before.points.length; i++)
      for (const key of ["x", "y", "z_bottom", "z_top"] as const)
        maxError = Math.max(maxError, Math.abs(before.points[i]![key] - after.points[i]![key]));
    const { points: _a, ...flagsBefore } = before,
      { points: _b, ...flagsAfter } = after;
    if (JSON.stringify(flagsBefore) !== JSON.stringify(flagsAfter))
      throw new Error(`Obstacle flags changed: ${part.id}`);
  }
  if (maxError > 0.001) throw new Error(`Map ${doc.map}: footprint drift ${maxError}`);
  doc.assetSources = [...references.values()];
  doc.sceneAssets = item.ground.map((ground: { id: string }) => ({
    ...ground,
    ...plan.references[ground.id],
  }));
  const metadata = { ...item.metadata };
  delete metadata.assetOrigins;
  doc.sceneMetadata = metadata;
  parseLevel3D(doc);
  const destination = path.join(plan.output, item.file);
  await fs.mkdir(path.dirname(destination), { recursive: true });
  const instanceDescriptors = new Map<string, ProjectionAssetDescriptor>();
  for (const reference of references.values())
    instanceDescriptors.set(
      reference.id,
      descriptorForSource(
        reference,
        await descriptor(reference.id.replace(/--state-(initial|applied)$/, "")),
      ),
    );
  await fs.writeFile(
    destination,
    JSON.stringify(serializeStoredMap(doc, instanceDescriptors), null, 2) + "\n",
  );
  const result = {
    map: doc.map,
    parts: doc.objects.length,
    assets: references.size,
    maxFootprintError: maxError,
  };
  console.log(result);
  report.push(result);
}
await fs.writeFile(
  path.join(path.dirname(process.argv[2]!), "placement-proof.json"),
  JSON.stringify(report, null, 2) + "\n",
);
