/**
 * Derived browser release models (`release_model` in the asset index) sit next to published
 * models. A `<release>.receipt.json` binds each one to the exact source bytes it was built from;
 * saved maps keep pinning the published model, so a release is used only while its receipt names
 * that pinned hash. A stale release (source republished, release not rebuilt yet) falls back to
 * the published model with a warning; a missing or corrupted release is a broken library.
 */

export async function sha256(bytes: ArrayBuffer): Promise<string> {
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), b => b.toString(16).padStart(2, "0")).join("");
}

/** Release bytes when their receipt names `sourceSha256`, otherwise null (use the original). */
export async function readReleaseModel(read: (path: string) => Promise<File>, release: string,
  sourceSha256: string): Promise<ArrayBuffer | null> {
  const receipt: unknown = JSON.parse(await (await read(`${release}.receipt.json`)).text());
  if (!receipt || typeof receipt !== "object" || typeof (receipt as { source?: unknown }).source !== "string" ||
      typeof (receipt as { output?: unknown }).output !== "string") throw new Error(`Invalid release receipt: ${release}`);
  const { source, output } = receipt as { source: string; output: string };
  if (source !== sourceSha256) {
    console.warn(`Release model was built from another source revision; loading the published model: ${release}`);
    return null;
  }
  const bytes = await (await read(release)).arrayBuffer();
  if (await sha256(bytes) !== output) throw new Error(`Release model does not match its receipt: ${release}`);
  return bytes;
}

/** Only self-contained GLBs have release derivatives. */
export function releaseApplies(model: string, resources: readonly unknown[] | undefined): boolean {
  return model.endsWith(".glb") && !resources?.length;
}
