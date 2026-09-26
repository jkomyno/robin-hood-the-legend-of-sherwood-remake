/** Select one named scene in a JSON glTF before decoding its resources. */
export function selectGltfScene<T extends { scenes?: { name?: string }[]; scene?: number }>(json: T, name?: string): T {
  if (name === undefined) return json;
  const matches = (json.scenes ?? []).filter(scene => scene.name === name);
  if (matches.length !== 1) throw new Error(`glTF scene must exist exactly once: ${name}`);
  return { ...json, scenes: matches, scene: 0 };
}

/** Select before GLTFLoader parses: it eagerly creates every scene otherwise. */
export function selectGlbScene(bytes: ArrayBuffer, name?: string, modelPath?: string): ArrayBuffer {
  if (name === undefined && modelPath === undefined) return bytes;
  if (name !== undefined && (typeof name !== "string" || !name.trim())) throw new Error("Invalid GLB scene selector");
  const view = new DataView(bytes);
  if (bytes.byteLength < 20 || view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== bytes.byteLength)
    throw new Error("Invalid GLB header");
  const length = view.getUint32(12, true);
  if (view.getUint32(16, true) !== 0x4e4f534a || length % 4 || 20 + length > bytes.byteLength) throw new Error("Invalid GLB JSON chunk");
  const json = JSON.parse(new TextDecoder().decode(new Uint8Array(bytes, 20, length)));
  if (name !== undefined) {
    const matches = (json.scenes ?? []).filter((scene: { name?: string }) => scene.name === name);
    if (matches.length !== 1) throw new Error(`GLB scene must exist exactly once: ${name}`);
    json.scenes = matches;
    json.scene = 0;
  }
  if (modelPath !== undefined) resolveGltfResources(modelPath, json);
  // Node/accessor/bufferView indices and all remaining chunks remain unchanged.
  const encoded = new TextEncoder().encode(JSON.stringify(json));
  const padded = Math.ceil(encoded.length / 4) * 4;
  const output = new ArrayBuffer(20 + padded + bytes.byteLength - 20 - length);
  const target = new Uint8Array(output), header = new DataView(output);
  target.set(new Uint8Array(bytes, 0, 20));
  header.setUint32(8, output.byteLength, true); header.setUint32(12, padded, true);
  target.fill(32, 20, 20 + padded); target.set(encoded, 20);
  target.set(new Uint8Array(bytes, 20 + length), 20 + padded);
  return output;
}

/** Resolve standard model-relative payload URIs to pinned library paths. */
export function resolveGltfResources(model: string, json: any) {
  for (const table of [json.buffers ?? [], json.images ?? []]) for (const value of table) {
    if (typeof value.uri !== "string") continue;
    // Imported manifests previously used explicit library-relative payloads.
    if (value.uri.startsWith("3d-assets/")) continue;
    if (/[\\\0:#?%]/.test(value.uri)) throw new Error("Unsafe glTF resource URI");
    const segments = model.split("/").slice(0, -1);
    for (const segment of value.uri.split("/")) {
      if (segment === "..") { if (!segments.pop()) throw new Error("glTF resource escapes library"); }
      else if (segment !== "." && segment !== "") segments.push(segment);
    }
    value.uri = segments.join("/");
  }
  return json;
}
