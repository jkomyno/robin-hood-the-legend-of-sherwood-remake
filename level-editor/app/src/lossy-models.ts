/**
 * Derived lossy browser models (`lossy_model` in the asset index) sit next to published
 * models. A `<lossy_model>.receipt.json` binds each one to the exact source bytes it was built
 * from; saved maps keep pinning the published model, so a lossy model is used only while its
 * receipt names that pinned hash. A stale lossy model (source republished, not rebuilt yet)
 * falls back to the published model with a warning; a missing or corrupted one is a broken library.
 */

export async function sha256(bytes: ArrayBuffer): Promise<string> {
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), b => b.toString(16).padStart(2, "0")).join("");
}

/** Lossy bytes when their receipt names `sourceSha256`, otherwise null (use the original). */
export async function readLossyModel(read: (path: string) => Promise<File>, lossy: string,
  sourceSha256: string): Promise<ArrayBuffer | null> {
  const receipt: unknown = JSON.parse(await (await read(`${lossy}.receipt.json`)).text());
  if (!receipt || typeof receipt !== "object" || typeof (receipt as { source?: unknown }).source !== "string" ||
      typeof (receipt as { output?: unknown }).output !== "string") throw new Error(`Invalid lossy receipt: ${lossy}`);
  const { source, output } = receipt as { source: string; output: string };
  if (source !== sourceSha256) {
    console.warn(`Lossy model was built from another source revision; loading the published model: ${lossy}`);
    return null;
  }
  const bytes = await (await read(lossy)).arrayBuffer();
  if (await sha256(bytes) !== output) throw new Error(`Lossy model does not match its receipt: ${lossy}`);
  return bytes;
}

/** Lossy derivatives are self-contained GLBs (shared resources embedded); only GLB sources have them. */
export function lossyApplies(model: string): boolean {
  return model.endsWith(".glb");
}
