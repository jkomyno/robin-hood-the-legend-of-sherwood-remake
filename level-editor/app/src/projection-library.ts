import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "meshoptimizer";
import {
  assetNodeKey, assetVariantId, parseExternalAssetSources, parseProjectionAssetDescriptor,
  parseProjectionAssetIndex, safeLibraryPath,
  type ExternalAssetSource, type ProjectionAssetDescriptor, type ProjectionAssetEntry,
} from "@rle/shared";
import { isNotFound, readJson, subdir } from "./fs.ts";
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
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), b => b.toString(16).padStart(2, "0")).join("");
}

function previewLoader() {
  return new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
}

/** The projection-model index is separate from the cutout library index. */
export async function listProjectionAssets(root: FileSystemDirectoryHandle, map?: string): Promise<ProjectionAssetEntry[]> {
  const dir = await subdir(root, ["3d-assets"]);
  if (!dir) return [];
  let index: unknown;
  try { index = await readJson(dir, "index.json"); }
  catch (error) { if (isNotFound(error)) return []; throw error; }
  const entries = parseProjectionAssetIndex(index).filter(entry => (!map || entry.source_map.toLowerCase() === map.toLowerCase()))
    .map(entry => ({ ...entry, descriptor: `3d-assets/${entry.descriptor}`, model: `3d-assets/${entry.model}`,
      ...(entry.preview_model ? { preview_model: `3d-assets/${entry.preview_model}` } : {}) }));
  const expanded = await Promise.all(entries.map(async entry => {
    const descriptor = parseProjectionAssetDescriptor(JSON.parse(await (await libraryFile(root, entry.descriptor)).text()));
    if (descriptor.id !== entry.id || descriptor.source_map.toLowerCase() !== entry.source_map.toLowerCase()) throw new Error(`Asset catalog identity mismatch: ${entry.id}`);
    const variants = descriptor.state_variants ?? descriptor.standalone_variants;
    if (!variants) return [entry];
    const parent = entry.descriptor.split("/").slice(0, -1).join("/");
    return [...(descriptor.standalone_variants ? [entry] : []), ...(["initial", "applied"] as const).flatMap(state => {
      const variant = variants[state];
      return variant ? [{ ...entry, id: assetVariantId(entry.id, state), name: `${entry.name} — ${variant.name} (static)`,
        state_variant: state, model: `${parent}/${variant.model}`, preview_model: undefined }] : [];
    })];
  }));
  const flattened = expanded.flat();
  if (new Set(flattened.map(entry => entry.id)).size !== flattened.length) throw new Error("Duplicate static asset variant identity");
  return flattened;
}

export interface PreparedProjectionAsset {
  descriptor: ProjectionAssetDescriptor;
  reference: ExternalAssetSource;
  asset: THREE.Object3D;
  sources: Map<string, THREE.Object3D>;
}

/** Owns resources until the caller adopts the result. Failed loads clean up. */
export async function prepareProjectionAsset(
  root: FileSystemDirectoryHandle,
  entry: Pick<ProjectionAssetEntry, "id" | "descriptor" | "model" | "state_variant">,
  _map: string,
  expected?: ExternalAssetSource,
): Promise<PreparedProjectionAsset> {
  if (expected) parseExternalAssetSources([expected]);
  const descriptorBytes = await (await libraryFile(root, entry.descriptor)).arrayBuffer();
  const descriptorHash = await hash(descriptorBytes);
  if (expected && expected.descriptor_sha256 !== descriptorHash) throw new Error(`Asset descriptor changed: ${entry.id}`);
  const original = parseProjectionAssetDescriptor(JSON.parse(new TextDecoder().decode(descriptorBytes)));
  const variant = entry.state_variant ? (original.state_variants ?? original.standalone_variants)?.[entry.state_variant] : undefined;
  if (entry.state_variant && !variant) throw new Error(`Unknown static asset variant: ${entry.state_variant}`);
  const descriptor = variant ? { ...original, id: assetVariantId(original.id, entry.state_variant!),
    name: `${original.name} — ${variant.name}`, model: variant.model, parts: variant.parts ?? original.parts, state_variants: undefined, standalone_variants: undefined } : original;
  if (descriptor.id !== entry.id)
    throw new Error(`Asset identity mismatch: ${entry.id}`);
  if (descriptor.editor_usage === "map-background") throw new Error("Map backgrounds are part of the map and cannot be inserted as objects");
  const parent = entry.descriptor.split("/").slice(0, -1).join("/");
  const modelPath = parent ? `${parent}/${descriptor.model}` : descriptor.model;
  if (modelPath !== entry.model) throw new Error(`Asset model path mismatch: ${entry.id}`);
  const modelBytes = await (await libraryFile(root, entry.model)).arrayBuffer();
  const modelHash = await hash(modelBytes);
  if (expected && expected.model_sha256 !== modelHash) throw new Error(`Asset model changed: ${entry.id}`);
  const reference = { id: entry.id, descriptor: entry.descriptor, model: entry.model,
    descriptor_sha256: descriptorHash, model_sha256: modelHash,
    ...(entry.state_variant ? { state_variant: entry.state_variant } : {}) };
  parseExternalAssetSources([reference]);
  let asset: THREE.Object3D | null = null;
  try {
    const gltf = await new GLTFLoader().parseAsync(modelBytes, "");
    asset = gltf.scene;
    const mapRoot = asset.children.find(child => child.name === "map");
    if (!mapRoot || mapRoot.children.length !== 1) throw new Error(`Standalone asset requires exactly one group: ${entry.id}`);
    const group = mapRoot.children[0]!;
    if (group.userData.asset_group !== original.id) throw new Error(`Standalone group mismatch: ${entry.id}`);
    // Children below the map wrapper are Z-up. Their transforms must match the
    // local collision frame; the exporter bakes all parent transforms in meshes.
    const identity = new THREE.Matrix4();
    group.updateMatrix();
    if (!group.matrix.equals(identity)) throw new Error(`Standalone group has an unbaked transform: ${entry.id}`);
    const sources = new Map<string, THREE.Object3D>();
    const parts = new Map(descriptor.parts.map(part => [part.node, part]));
    for (const node of group.children) {
      const part = parts.get(node.name);
      const key = assetNodeKey(entry.id, node.name);
      if (!part || sources.has(key) || node.userData.source_obstacle !== part.source_obstacle ||
          JSON.stringify(node.userData.source_components) !== JSON.stringify(part.source_components) ||
          (part.mission_profile !== undefined && node.userData.mission_patch_profile !== part.mission_profile))
        throw new Error(`Unexpected or duplicate standalone part: ${node.name}`);
      let meshes = 0;
      node.traverse(child => { if ((child as THREE.Mesh).isMesh) meshes++; });
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
export async function loadProjectionAssetPreview(root: FileSystemDirectoryHandle, entry: ProjectionAssetEntry): Promise<THREE.Object3D> {
  if (entry.editor_usage === "map-background") {
    const bytes = await (await libraryFile(root, entry.model)).arrayBuffer();
    return (await new GLTFLoader().parseAsync(bytes, "")).scene;
  }
  if (entry.preview_model) {
    const preview = (await previewLoader().parseAsync(await (await libraryFile(root, entry.preview_model)).arrayBuffer(), "")).scene;
    const mapRoot = preview.children.find(child => child.name === "map");
    const group = mapRoot?.children[0];
    if (group) for (const part of parseProjectionAssetDescriptor(JSON.parse(await (await libraryFile(root, entry.descriptor)).text())).parts) {
      const node = group.children.find(child => child.name === part.node);
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
