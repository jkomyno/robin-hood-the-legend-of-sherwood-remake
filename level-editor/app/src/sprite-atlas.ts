/** Decoded atlas images are shared across poses while a mission preview is built. */
export class SpriteAtlasImages {
  private images = new Map<string, Promise<ImageBitmap>>();
  get(directory: FileSystemDirectoryHandle, key: string, filename: string) {
    if (!filename || /[\\/]/.test(filename) || filename === "." || filename === "..")
      throw new Error("Invalid sprite atlas path");
    const identity = key + "/" + filename;
    let image = this.images.get(identity);
    if (!image) {
      image = directory
        .getFileHandle(filename)
        .then(async (file) => createImageBitmap(await file.getFile()));
      this.images.set(identity, image);
    }
    return image;
  }
  dispose() {
    for (const image of this.images.values())
      void image.then(
        (bitmap) => bitmap.close(),
        () => {},
      );
    this.images.clear();
  }
}

export function spriteAtlasRect(
  value: unknown,
  width: number,
  height: number,
): [number, number, number, number] {
  if (!Array.isArray(value) || value.length !== 4 || value.some((n) => !Number.isSafeInteger(n)))
    throw new Error("Invalid sprite atlas rectangle");
  const [x, y, w, h] = value as [number, number, number, number];
  if (x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > width || y + h > height)
    throw new Error("Sprite atlas rectangle is outside the image");
  return [x, y, w, h];
}
