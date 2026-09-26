import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { documentProvenance, parseLevel3D, parseSceneDoc } from "@rle/shared";
import { listFiles, writeText } from "./fs.ts";
import { disposeObjectResources } from "./resources.ts";

export function validateNewMap(name: string) {
  name = name.trim();
  if (!/^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$/.test(name))
    throw new Error("Use 1–64 letters, numbers, spaces, hyphens or underscores; start with a letter or number.");
  return name;
}

/** Publish the model last so the level picker only discovers complete maps. */
export async function createNewMap(library: FileSystemDirectoryHandle, rawName: string) {
  const name = validateNewMap(rawName);
  const directory = await library.getDirectoryHandle("scenes", { create: true });
  const modelName = `${name}-volumes.scene.glb`;
  const sceneName = `${name}-volumes.scene.json`;
  const documentName = `${name}.level3d.json`;
  const names = [sceneName, documentName, modelName];
  const existing = new Set((await listFiles(directory)).map(file => file.toLowerCase()));
  if (names.some(file => existing.has(file.toLowerCase())))
    throw new Error(`A map named “${name}” already exists. Choose a different name.`);

  const camera = { kind: "oblique-orthographic" as const, elevation_deg: 35 };
  const scene = parseSceneDoc({ version: 1, standalone: true, map: name, size: null, camera, placements: [] });
  const root = new THREE.Group();
  root.name = "map";
  let bytes: ArrayBuffer;
  try {
    const result = await new GLTFExporter().parseAsync(root, { binary: true });
    if (!(result instanceof ArrayBuffer)) throw new Error("Map export did not produce a binary model");
    bytes = result;
  } finally {
    disposeObjectResources([root]);
  }
  const document = parseLevel3D({ version: 1, map: name, size: null, camera,
    glb: modelName, groups: [], objects: [], provenance: await documentProvenance(null, bytes) });
  const created: string[] = [];
  try {
    created.push(sceneName);
    await writeText(directory, sceneName, JSON.stringify(scene, null, 2));
    created.push(documentName);
    await writeText(directory, documentName, JSON.stringify(document, null, 2));
    created.push(modelName);
    const file = await directory.getFileHandle(modelName, { create: true });
    const stream = await file.createWritable();
    try {
      await stream.write(bytes);
      await stream.close();
    } catch (error) {
      try { await stream.abort(); } catch { /* A failed close may already have released the stream. */ }
      throw error;
    }
  } catch (error) {
    const cleanup = await Promise.allSettled(created.map(file => directory.removeEntry(file)));
    const failures = cleanup.filter(result => result.status === "rejected");
    if (failures.length) throw new AggregateError([error, ...failures.map(result => result.reason)], "Map creation failed and incomplete files could not be removed");
    throw error;
  }
  return name;
}
