import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "meshoptimizer";
import {
  assetNodeKey,
  assetVariantId,
  descriptorForSource,
  parseExternalAssetSources,
  parseProjectionAssetDescriptor,
  parseProjectionAssetIndex,
  safeLibraryPath,
  selectGlbScene,
  type ExternalAssetSource,
  type ProjectionAssetDescriptor,
  type ProjectionAssetEntry,
} from "@rle/shared";
import { isNotFound, readJson, subdir } from "./fs.ts";
import { SceneAssetLoader } from "./scene-assets.ts";
import { readLossyModel, lossyApplies } from "./lossy-models.ts";
import { disposeObjectResources } from "./resources.ts";

async function libraryFile(root: FileSystemDirectoryHandle, path: string): Promise<File> {
  if (!safeLibraryPath(path)) throw new Error(`Unsafe library path: ${path}`);
  const parts = path.split("/");
  const name = parts.pop()!;
  const dir = await subdir(root, parts);
  if (!dir) throw new Error(`Missing asset directory: ${path}`);
  return (await dir.getFileHandle(name)).getFile();
}

async function hash(bytes: ArrayBuffer): Promise<string> {
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
}

function restoreNodeNames(gltf: Awaited<ReturnType<GLTFLoader["parseAsync"]>>) {
  gltf.scene.traverse((node) => {
    const index = gltf.parser?.associations.get(node)?.nodes;
    if (index !== undefined) {
      const name = gltf.parser.json.nodes[index]?.name;
      if (typeof name === "string") node.name = name;
    }
  });
}

function previewLoader() {
  return new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
}

/** The projection-model index is separate from the cutout library index. */
export async function listProjectionAssets(
  root: FileSystemDirectoryHandle,
  map?: string,
): Promise<ProjectionAssetEntry[]> {
  const dir = await subdir(root, ["3d-assets"]);
  if (!dir) return [];
  let index: unknown;
  try {
    index = await readJson(dir, "index.json");
  } catch (error) {
    if (isNotFound(error)) return [];
    throw error;
  }
  const entries = parseProjectionAssetIndex(index)
    .filter((entry) => !map || entry.source_map.toLowerCase() === map.toLowerCase())
    .map((entry) => ({
      ...entry,
      descriptor: `3d-assets/${entry.descriptor}`,
      model: `3d-assets/${entry.model}`,
      ...(entry.preview_model ? { preview_model: `3d-assets/${entry.preview_model}` } : {}),
      ...(entry.lossy_model ? { lossy_model: `3d-assets/${entry.lossy_model}` } : {}),
    }));
  return entries;
}

/** Read alternate appearances only for a card the user opens, not for every catalog entry. */
export async function listProjectionAppearances(
  root: FileSystemDirectoryHandle,
  entry: ProjectionAssetEntry,
): Promise<ProjectionAssetEntry[]> {
  const descriptor = parseProjectionAssetDescriptor(
    JSON.parse(await (await libraryFile(root, entry.descriptor)).text()),
  );
  if (
    descriptor.id !== entry.id ||
    descriptor.source_map.toLowerCase() !== entry.source_map.toLowerCase()
  )
    throw new Error(`Asset catalog identity mismatch: ${entry.id}`);
  if (entry.model_scene !== descriptor.model_scene)
    throw new Error(`Asset catalog scene mismatch: ${entry.id}`);
  const variants = descriptor.state_variants ?? descriptor.standalone_variants;
  if (!variants) return [entry];
  const parent = entry.descriptor.split("/").slice(0, -1).join("/");
  return [
    ...(descriptor.standalone_variants ? [entry] : []),
    ...(["initial", "applied"] as const).flatMap((state) => {
      const variant = variants[state];
      return variant
        ? [
            {
              ...entry,
              id: assetVariantId(entry.id, state),
              name: variant.name,
              state_variant: state,
              model: `${parent}/${variant.model}`,
              model_scene: variant.model_scene,
              preview_model:
                variant.model === descriptor.model && variant.model_scene
                  ? entry.preview_model
                  : undefined,
              lossy_model: variant.model === descriptor.model ? entry.lossy_model : undefined,
              model_sha256: variant.model === descriptor.model ? entry.model_sha256 : undefined,
            },
          ]
        : [];
    }),
  ];
}

/** Library model path -> lossy model path, both prefixed like saved references. */
export async function listLossyModels(
  root: FileSystemDirectoryHandle,
): Promise<Map<string, string>> {
  const dir = await subdir(root, ["3d-assets"]);
  if (!dir) return new Map();
  let index: unknown;
  try {
    index = await readJson(dir, "index.json");
  } catch (error) {
    if (isNotFound(error)) return new Map();
    throw error;
  }
  return new Map(
    parseProjectionAssetIndex(index).flatMap((entry) =>
      entry.lossy_model
        ? [[`3d-assets/${entry.model}`, `3d-assets/${entry.lossy_model}`] as const]
        : [],
    ),
  );
}

export interface PreparedProjectionAsset {
  descriptor: ProjectionAssetDescriptor;
  reference: ExternalAssetSource;
  asset: THREE.Object3D;
  sources: Map<string, THREE.Object3D>;
}

/** Owns resources until the caller adopts the result. Failed loads clean up. */
export async function readPinnedAssetDescriptors(
  root: FileSystemDirectoryHandle,
  references: ExternalAssetSource[],
): Promise<Map<string, ProjectionAssetDescriptor>> {
  parseExternalAssetSources(references);
  return new Map(
    await Promise.all(
      references.map(async (reference) => {
        const bytes = await (await libraryFile(root, reference.descriptor)).arrayBuffer();
        if ((await hash(bytes)) !== reference.descriptor_sha256)
          throw new Error(`Asset descriptor changed: ${reference.id}`);
        const descriptor = descriptorForSource(
          reference,
          JSON.parse(new TextDecoder().decode(bytes)),
        );
        return [reference.id, descriptor] as const;
      }),
    ),
  );
}

export async function prepareProjectionAsset(
  root: FileSystemDirectoryHandle,
  entry: Pick<
    ProjectionAssetEntry,
    "id" | "descriptor" | "model" | "state_variant" | "model_scene" | "lossy_model" | "model_sha256"
  >,
  _map: string,
  expected?: ExternalAssetSource,
  sharedLoader?: SceneAssetLoader,
): Promise<PreparedProjectionAsset> {
  if (expected) parseExternalAssetSources([expected]);
  const descriptorBytes = await (await libraryFile(root, entry.descriptor)).arrayBuffer();
  const descriptorHash = await hash(descriptorBytes);
  if (expected && expected.descriptor_sha256 !== descriptorHash)
    throw new Error(`Asset descriptor changed: ${entry.id}`);
  const original = parseProjectionAssetDescriptor(
    JSON.parse(new TextDecoder().decode(descriptorBytes)),
  );
  const variant = entry.state_variant
    ? (original.state_variants ?? original.standalone_variants)?.[entry.state_variant]
    : undefined;
  if (entry.state_variant && !variant)
    throw new Error(`Unknown static asset variant: ${entry.state_variant}`);
  const descriptor = variant
    ? {
        ...original,
        id: assetVariantId(original.id, entry.state_variant!),
        name: `${original.name} — ${variant.name}`,
        model: variant.model,
        model_scene: variant.model_scene,
        parts: variant.parts ?? original.parts,
        state_variants: undefined,
        standalone_variants: undefined,
      }
    : original;
  if (descriptor.id !== entry.id) throw new Error(`Asset identity mismatch: ${entry.id}`);
  if (descriptor.editor_usage === "map-background")
    throw new Error("Map backgrounds are part of the map and cannot be inserted as objects");
  const parent = entry.descriptor.split("/").slice(0, -1).join("/");
  const modelPath = parent ? `${parent}/${descriptor.model}` : descriptor.model;
  if (entry.model_scene !== descriptor.model_scene)
    throw new Error(`Asset model scene mismatch: ${entry.id}`);
  if (
    expected &&
    ["id", "descriptor", "model", "state_variant", "model_scene"].some(
      (key) => expected[key as keyof ExternalAssetSource] !== entry[key as keyof typeof entry],
    )
  )
    throw new Error(`Asset saved reference mismatch: ${entry.id}`);
  if (modelPath !== entry.model) throw new Error(`Asset model path mismatch: ${entry.id}`);
  // Deployments can supply the verified source hash without serving original model bytes.
  // Local catalogs without that hash still read the original for new insertions.
  const lossy = entry.lossy_model && lossyApplies(entry.model) ? entry.lossy_model : undefined;
  const read = (path: string) => libraryFile(root, path);
  if (expected && entry.model_sha256 && expected.model_sha256 !== entry.model_sha256)
    throw new Error(`Asset model changed: ${entry.id}`);
  const sourceHash = entry.model_sha256 ?? expected?.model_sha256;
  let lossyBytes = lossy && sourceHash ? await readLossyModel(read, lossy) : null;
  let modelBytes: ArrayBuffer | null = null,
    modelHash: string;
  if (lossyBytes) modelHash = sourceHash!;
  else {
    modelBytes = await (await libraryFile(root, entry.model)).arrayBuffer();
    modelHash = await hash(modelBytes);
    if (expected && expected.model_sha256 !== modelHash)
      throw new Error(`Asset model changed: ${entry.id}`);
    if (lossy && !expected) lossyBytes = await readLossyModel(read, lossy);
  }
  const displayBytes = (lossyBytes ?? modelBytes)!;
  const resourcePins = (resources: ExternalAssetSource["resources"]) =>
    (resources ?? [])
      .map((resource) => `${resource.path}:${resource.sha256}`)
      .sort()
      .join("\n");
  if (expected && resourcePins(expected.resources) !== resourcePins(descriptor.resources))
    throw new Error(`Asset saved resource pins mismatch: ${entry.id}`);
  const reference = {
    id: entry.id,
    descriptor: entry.descriptor,
    model: entry.model,
    descriptor_sha256: descriptorHash,
    model_sha256: modelHash,
    ...(descriptor.resources ? { resources: descriptor.resources } : {}),
    ...(entry.model_scene ? { model_scene: entry.model_scene } : {}),
    ...(entry.state_variant ? { state_variant: entry.state_variant } : {}),
  };
  parseExternalAssetSources([reference]);
  let asset: THREE.Object3D | null = null;
  try {
    if (entry.model.endsWith(".gltf") || descriptor.resources !== undefined) {
      const loader = sharedLoader ?? new SceneAssetLoader(root);
      try {
        asset = await loader.load(
          { ...reference, role: "objects", resources: descriptor.resources ?? [] },
          lossyBytes ?? undefined,
        );
      } finally {
        if (!sharedLoader) loader.dispose();
      }
    } else {
      const gltf = await new GLTFLoader().parseAsync(
        selectGlbScene(displayBytes, entry.model_scene),
        "",
      );
      asset = gltf.scene;
      restoreNodeNames(gltf);
    }
    const mapRoot = asset.children.find((child) => child.name === "map");
    if (!mapRoot || mapRoot.children.length !== 1)
      throw new Error(`Standalone asset requires exactly one group: ${entry.id}`);
    const group = mapRoot.children[0]!;
    if (group.userData.asset_group !== original.id)
      throw new Error(`Standalone group mismatch: ${entry.id}`);
    // Children below the map wrapper are Z-up. Their transforms must match the
    // local collision frame; the exporter bakes all parent transforms in meshes.
    const identity = new THREE.Matrix4();
    group.updateMatrix();
    if (!group.matrix.equals(identity))
      throw new Error(`Standalone group has an unbaked transform: ${entry.id}`);
    const sources = new Map<string, THREE.Object3D>();
    const parts = new Map(descriptor.parts.map((part) => [part.node, part]));
    for (const node of group.children) {
      const part = parts.get(node.name);
      const key = assetNodeKey(entry.id, node.name);
      if (
        !part ||
        sources.has(key) ||
        node.userData.source_obstacle !== part.source_obstacle ||
        JSON.stringify(node.userData.source_components) !==
          JSON.stringify(part.source_components) ||
        (part.mission_profile !== undefined &&
          node.userData.mission_patch_profile !== part.mission_profile) ||
        (part.scenery !== undefined) !== (node.userData.scenery === true)
      )
        throw new Error(`Unexpected or duplicate standalone part: ${node.name}`);
      let meshes = 0;
      node.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) meshes++;
      });
      if (!meshes) throw new Error(`Standalone part has no mesh: ${node.name}`);
      sources.set(key, node);
    }
    if (sources.size !== parts.size) throw new Error(`Missing standalone asset parts: ${entry.id}`);
    return { descriptor, reference, asset, sources };
  } catch (error) {
    if (asset) disposeObjectResources([asset]);
    throw error;
  }
}

/** The caller owns preview model resources and must dispose them when retired. */
export async function loadProjectionAssetPreview(
  root: FileSystemDirectoryHandle,
  entry: ProjectionAssetEntry,
): Promise<THREE.Object3D> {
  if (entry.editor_usage === "map-background") {
    const descriptor = parseProjectionAssetDescriptor(
      JSON.parse(await (await libraryFile(root, entry.descriptor)).text()),
    );
    const bytes = await (await libraryFile(root, entry.model)).arrayBuffer();
    const loader = new SceneAssetLoader(root);
    try {
      return await loader.load({
        id: entry.id,
        role: "ground",
        model: entry.model,
        model_scene: entry.model_scene,
        model_sha256: await hash(bytes),
        resources: descriptor.resources ?? [],
      });
    } finally {
      loader.dispose();
    }
  }
  if (entry.preview_model) {
    const original = parseProjectionAssetDescriptor(
      JSON.parse(await (await libraryFile(root, entry.descriptor)).text()),
    );
    const variant = entry.state_variant
      ? (original.state_variants ?? original.standalone_variants)?.[entry.state_variant]
      : undefined;
    if (entry.state_variant && !variant)
      throw new Error(`Unknown static asset variant: ${entry.state_variant}`);
    if (entry.model_scene !== (variant ? variant.model_scene : original.model_scene))
      throw new Error(`Asset preview scene mismatch: ${entry.id}`);
    const bytes = await (await libraryFile(root, entry.preview_model)).arrayBuffer();
    let selected: ArrayBuffer;
    try {
      selected = selectGlbScene(bytes, entry.model_scene);
    } catch (error) {
      // An older preview may predate the shared state file; use the exact full model.
      if (!entry.model_scene) throw error;
      const prepared = await prepareProjectionAsset(root, entry, entry.source_map);
      for (const part of prepared.descriptor.parts)
        prepared.sources.get(assetNodeKey(prepared.descriptor.id, part.node))!.visible =
          !part.default_hidden;
      return prepared.asset;
    }
    const gltf = await previewLoader().parseAsync(selected, "");
    restoreNodeNames(gltf);
    const preview = gltf.scene;
    const mapRoot = preview.children.find((child) => child.name === "map");
    const group = mapRoot?.children[0];
    if (group)
      for (const part of variant?.parts ?? original.parts) {
        const node = group.children.find((child) => child.name === part.node);
        if (node) node.visible = !part.default_hidden;
      }
    return preview;
  }
  const prepared = await prepareProjectionAsset(root, entry, entry.source_map);
  for (const part of prepared.descriptor.parts) {
    const node = prepared.sources.get(assetNodeKey(prepared.descriptor.id, part.node));
    if (node) node.visible = !part.default_hidden;
  }
  return prepared.asset;
}
