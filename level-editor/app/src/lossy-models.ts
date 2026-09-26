/** Lossy models are validated against their sources when the asset index is published. */
export async function readLossyModel(
  read: (path: string) => Promise<File>,
  lossy: string,
): Promise<ArrayBuffer> {
  return (await read(lossy)).arrayBuffer();
}

/** Lossy derivatives are self-contained GLBs (shared resources embedded); only GLB sources have them. */
export function lossyApplies(model: string): boolean {
  return model.endsWith(".glb");
}
