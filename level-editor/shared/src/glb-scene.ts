/** Select before GLTFLoader parses: it eagerly creates every scene otherwise. */
export function selectGlbScene(bytes: ArrayBuffer, name?: string): ArrayBuffer {
  if (name === undefined) return bytes;
  if (typeof name !== "string" || !name.trim()) throw new Error("Invalid GLB scene selector");
  const view = new DataView(bytes);
  if (bytes.byteLength < 20 || view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== bytes.byteLength)
    throw new Error("Invalid GLB header");
  const length = view.getUint32(12, true);
  if (view.getUint32(16, true) !== 0x4e4f534a || length % 4 || 20 + length > bytes.byteLength) throw new Error("Invalid GLB JSON chunk");
  const json = JSON.parse(new TextDecoder().decode(new Uint8Array(bytes, 20, length)));
  const matches = (json.scenes ?? []).filter((scene: { name?: string }) => scene.name === name);
  if (matches.length !== 1) throw new Error(`GLB scene must exist exactly once: ${name}`);
  json.scenes = matches;
  json.scene = 0;
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
