import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import {
  assetNodeKey, parseExternalAssetSources, parseProjectionAssetDescriptor,
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

/** The projection-model index is separate from the cutout library index. */
export async function listProjectionAssets(root: FileSystemDirectoryHandle, map: string): Promise<ProjectionAssetEntry[]> {
  const dir = await subdir(root, ["3d-assets"]);
  if (!dir) return [];
  let index: unknown;
  try { index = await readJson(dir, "index.json"); }
  catch (error) { if (isNotFound(error)) return []; throw error; }
  return parseProjectionAssetIndex(index).filter(entry => entry.source_map.toLowerCase() === map.toLowerCase())
    .map(entry => ({ ...entry, descriptor: `3d-assets/${entry.descriptor}`, model: `3d-assets/${entry.model}` }));
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
  entry: Pick<ProjectionAssetEntry, "id" | "descriptor" | "model">,
  map: string,
  expected?: ExternalAssetSource,
): Promise<PreparedProjectionAsset> {
  if (expected) parseExternalAssetSources([expected]);
  const descriptorBytes = await (await libraryFile(root, entry.descriptor)).arrayBuffer();
  const descriptorHash = await hash(descriptorBytes);
  if (expected && expected.descriptor_sha256 !== descriptorHash) throw new Error(`Asset descriptor changed: ${entry.id}`);
  const descriptor = parseProjectionAssetDescriptor(JSON.parse(new TextDecoder().decode(descriptorBytes)));
  if (descriptor.id !== entry.id || descriptor.source_map.toLowerCase() !== map.toLowerCase())
    throw new Error(`Asset identity or source map mismatch: ${entry.id}`);
  const parent = entry.descriptor.split("/").slice(0, -1).join("/");
  const modelPath = parent ? `${parent}/${descriptor.model}` : descriptor.model;
  if (modelPath !== entry.model) throw new Error(`Asset model path mismatch: ${entry.id}`);
  const modelBytes = await (await libraryFile(root, entry.model)).arrayBuffer();
  const modelHash = await hash(modelBytes);
  if (expected && expected.model_sha256 !== modelHash) throw new Error(`Asset model changed: ${entry.id}`);
  const reference = { id: entry.id, descriptor: entry.descriptor, model: entry.model,
    descriptor_sha256: descriptorHash, model_sha256: modelHash };
  parseExternalAssetSources([reference]);
  let asset: THREE.Object3D | null = null;
  try {
    const gltf = await new GLTFLoader().parseAsync(modelBytes, "");
    asset = gltf.scene;
    const mapRoot = asset.children.find(child => child.name === "map");
    if (!mapRoot || mapRoot.children.length !== 1) throw new Error(`Standalone asset requires exactly one group: ${entry.id}`);
    const group = mapRoot.children[0]!;
    if (group.userData.asset_group !== entry.id) throw new Error(`Standalone group mismatch: ${entry.id}`);
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
      if (!part || sources.has(key) || node.userData.source_obstacle !== part.source_obstacle)
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
