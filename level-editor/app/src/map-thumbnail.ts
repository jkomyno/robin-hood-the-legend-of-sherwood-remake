import { isNotFound } from "./fs";

export const thumbnailExtensions = ["avif", "webp", "png"] as const;

/** Canvas silently returns PNG for unsupported types; inspect the actual result. */
export async function encodeMapThumbnail(canvas: HTMLCanvasElement): Promise<Blob> {
  const encode = (type: string) =>
    new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error("Thumbnail encoding failed"))),
        type,
        0.6,
      );
    });
  const avif = await encode("image/avif");
  if (avif.type === "image/avif") return avif;
  return encode("image/webp");
}

export async function writeMapThumbnail(
  directory: FileSystemDirectoryHandle,
  name: string,
  blob: Blob,
) {
  const extension = thumbnailExtensions.find((ext) => blob.type === `image/${ext}`);
  if (!extension) throw new Error(`Unsupported thumbnail format: ${blob.type}`);
  const file = await directory.getFileHandle(`${name}.${extension}`, { create: true });
  const writer = await file.createWritable();
  try {
    await writer.write(blob);
    await writer.close();
  } catch (error) {
    await writer.abort().catch(() => {});
    throw error;
  }
  // Remove older encodings so a browser capability change cannot show stale previews.
  for (const other of thumbnailExtensions) {
    if (other === extension) continue;
    try {
      await directory.removeEntry(`${name}.${other}`);
    } catch (error) {
      if (!isNotFound(error)) throw error;
    }
  }
}
