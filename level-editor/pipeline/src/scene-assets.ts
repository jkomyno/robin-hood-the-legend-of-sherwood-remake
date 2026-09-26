import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { safeLibraryPath, type SceneAssetSource, type Level3D } from "@rle/shared";

export async function readSceneAsset(library: string, reference: SceneAssetSource, verified = new Set<string>()) {
  const checked = async (name: string, expected: string) => {
    if (!safeLibraryPath(name)) throw new Error(`Unsafe asset path: ${name}`);
    const bytes = await fs.readFile(path.join(library,name));
    if (!verified.has(name+":"+expected) && createHash("sha256").update(bytes).digest("hex") !== expected) throw new Error(`Asset changed: ${name}`);
    verified.add(name+":"+expected);
    return bytes;
  };
  const bytes = await checked(reference.model,reference.model_sha256);
  const json = reference.model.endsWith(".gltf") ? JSON.parse(bytes.toString()) : JSON.parse(bytes.toString("utf8",20,20+bytes.readUInt32LE(12)));
  const resources: Record<string, Uint8Array<ArrayBuffer>> = {};
  for (const resource of reference.resources) resources[resource.path] = new Uint8Array(await checked(resource.path,resource.sha256));
  return { json, resources, bytes };
}
export async function loadSceneModel(library: string, reference: SceneAssetSource) {
  const {json,resources,bytes} = await readSceneAsset(library,reference);
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  return reference.model.endsWith(".gltf") ? io.readJSON({json,resources}) : io.readBinary(bytes);
}

/** Assemble only node metadata for ownership and native patch verification. */
export async function sceneAssetNodes(library: string, document: Level3D) {
  const verified = new Set<string>();
  const nodes: any[] = [{ name:"map",children:[] }];
  for (const reference of document.sceneAssets) {
    const resources = reference.resources.filter(resource => !verified.has(resource.path+":"+resource.sha256));
    const {json} = await readSceneAsset(library,{...reference,resources},verified);
    const offset = nodes.length;
    nodes.push(...(json.nodes ?? []).map((node: any) => ({ ...node,
      ...(node.children ? { children:node.children.map((index:number)=>index+offset) } : {}) })));
    let roots: number[] = json.scenes[json.scene ?? 0].nodes ?? [];
    if (roots.length===1 && json.nodes[roots[0]!].name==="map") roots=json.nodes[roots[0]!].children ?? [];
    nodes[0].children.push(...roots.map(index=>index+offset));
  }
  return { nodes };
}
