import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "meshoptimizer";
import { safeLibraryPath, selectGlbScene, selectGltfScene, resolveGltfResources, type SceneAssetSource } from "@rle/shared";
import { subdir } from "./fs.ts";
import { readReleaseModel, releaseApplies } from "./release-models.ts";

async function read(root: FileSystemDirectoryHandle, path: string) {
  if (!safeLibraryPath(path)) throw new Error(`Unsafe scene asset path: ${path}`);
  const parts = path.split("/");
  const name = parts.pop()!;
  const directory = await subdir(root, parts);
  if (!directory) throw new Error(`Missing scene asset directory: ${path}`);
  return (await directory.getFileHandle(name)).getFile();
}
async function checked(file: File, expected: string) {
  const bytes = await file.arrayBuffer();
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), byte => byte.toString(16).padStart(2, "0")).join("");
  if (hash !== expected) throw new Error(`Scene asset changed: ${file.name}`);
  return bytes;
}

/** One load owns shared payload URLs until every asset has finished decoding. */
export class SceneAssetLoader {
  private resources = new Map<string, Promise<string>>();
  private urls: string[] = [];
  private textures = new Map<string, Promise<THREE.Texture>>();
  private materials = new Map<string, Promise<THREE.Material>>();
  private finalMaterials = new Map<string, THREE.Material>();
  private root: FileSystemDirectoryHandle;
  private releases: ReadonlyMap<string, string>;
  /** `releases` maps pinned model paths to derived release models (see release-models.ts). */
  constructor(root: FileSystemDirectoryHandle, releases: ReadonlyMap<string, string> = new Map()) {
    this.root = root; this.releases = releases;
  }
  releaseFor(model: string): string | undefined { return this.releases.get(model); }
  /** `verifiedRelease`: release bytes the caller already bound to `reference.model_sha256`. */
  async load(reference: SceneAssetSource, verifiedRelease?: ArrayBuffer): Promise<THREE.Group> {
    const applies = releaseApplies(reference.model, reference.resources);
    if (verifiedRelease && !applies) throw new Error(`Release model cannot replace a resource-backed model: ${reference.model}`);
    const release = applies ? this.releases.get(reference.model) : undefined;
    let bytes = verifiedRelease ?? (release ? await readReleaseModel(path => read(this.root, path), release, reference.model_sha256) : null)
      ?? await checked(await read(this.root, reference.model), reference.model_sha256);
    if (reference.descriptor) await checked(await read(this.root, reference.descriptor), reference.descriptor_sha256!);
    if (reference.model.endsWith(".gltf")) bytes = new TextEncoder().encode(JSON.stringify(resolveGltfResources(reference.model, selectGltfScene(JSON.parse(new TextDecoder().decode(bytes)), reference.model_scene)))).buffer;
    else bytes = selectGlbScene(bytes, reference.model_scene, reference.resources.length ? reference.model : undefined);
    const urls = new Map<string, string>();
    await Promise.all(reference.resources.map(async resource => {
      const key = `${resource.path}:${resource.sha256}`;
      let pending = this.resources.get(key);
      if (!pending) {
        pending = (async () => {
          const file = await read(this.root, resource.path);
          const url = URL.createObjectURL(new Blob([await checked(file, resource.sha256)], { type: file.type }));
          this.urls.push(url);
          return url;
        })();
        this.resources.set(key, pending);
      }
      urls.set(resource.path, await pending);
    }));
    const manager = new THREE.LoadingManager();
    manager.setURLModifier(url => {
      const mapped = urls.get(url);
      if (mapped) return mapped;
      // Embedded GLB image URLs are allocated by GLTFLoader itself.
      if (url.startsWith("blob:")) return url;
      throw new Error(`Scene asset requested an unpinned resource: ${url}`);
    });
    const loader = new GLTFLoader(manager).setMeshoptDecoder(MeshoptDecoder);
    loader.register(parser => {
      // GLTFLoader creates geometry-specific material variants in a per-parser
      // cache. Share those variants too, so split meshes retain depth sorting.
      const assign = parser.assignFinalMaterial.bind(parser);
      parser.assignFinalMaterial = mesh => {
        const value = mesh as THREE.Mesh;
        const material = value.material as THREE.Material;
        const attributes = value.geometry.attributes;
        const key = [value.type, material.uuid, !!attributes.tangent, !!attributes.color, !!attributes.normal].join(":");
        const shared = this.finalMaterials.get(key);
        if (shared) value.material = shared;
        else { assign(mesh); this.finalMaterials.set(key, value.material as THREE.Material); }
      };
      const textureKey = (index: number) => {
        const texture = parser.json.textures[index];
        return JSON.stringify({ scope: parser.json.images[texture.source]?.uri ? undefined : reference.model_sha256, ...texture, source: parser.json.images[texture.source], sampler: parser.json.samplers?.[texture.sampler] });
      };
      return { name: "RLE_shared_asset_resources",
        loadTexture: (index: number) => {
          const key = textureKey(index);
          let result = this.textures.get(key);
          if (!result) { result = parser.loadTexture(index); this.textures.set(key, result); }
          return result;
        },
        loadMaterial: (index: number) => {
          const value = structuredClone(parser.json.materials[index]);
          for (const parent of [value, value.pbrMetallicRoughness ?? {}]) for (const [key, texture] of Object.entries(parent)) {
            if (key.endsWith("Texture") && texture && typeof texture === "object" && "index" in texture)
              texture.index = textureKey(texture.index as number);
          }
          const key = JSON.stringify(value);
          let result = this.materials.get(key);
          if (!result) { result = parser.loadMaterial(index); this.materials.set(key, result); }
          return result;
        },
      };
    });
    const result = await loader.parseAsync(bytes, "");
    result.scene.traverse(node => {
      const index = result.parser?.associations.get(node)?.nodes;
      const name = index === undefined ? undefined : result.parser.json.nodes[index]?.name;
      if (typeof name === "string") node.name = name;
    });
    return result.scene;
  }
  dispose() {
    for (const url of this.urls) URL.revokeObjectURL(url);
    this.urls = [];
    this.resources.clear();
  }
}
