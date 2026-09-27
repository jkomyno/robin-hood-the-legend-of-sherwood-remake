import type { Mask } from "../../shared/src/level.ts";

/** Decode authoring input strictly: a truncated mask must not become a valid
 * asset with silently missing coverage. Unwritten trailing blocks are empty. */
export function decodeRecoveryMask(mask: Pick<Mask, "box_size" | "mask_data">): Uint8Array {
  const [width, height] = mask.box_size;
  const data = mask.mask_data;
  if (
    !Number.isInteger(width) ||
    !Number.isInteger(height) ||
    width <= 0 ||
    height <= 0 ||
    width > 32767 ||
    height > 32767 ||
    width * height > 64 * 1024 * 1024
  )
    throw new Error("Invalid recovery mask dimensions");
  if (data.some((byte) => !Number.isInteger(byte) || byte < 0 || byte > 255))
    throw new Error("Invalid recovery mask byte");
  const pixels = new Uint8Array(width * height);
  let offset = 0;
  for (let y = 0; y < height; y++) {
    if (offset >= data.length) throw new Error(`Missing mask row ${y}`);
    const end = offset + 1 + data[offset++]!;
    if (end > data.length) throw new Error(`Truncated mask row ${y}`);
    let block = 0;
    while (offset < end) {
      const control = data[offset++]!;
      const count = control & 127;
      const repeat = (control & 128) !== 0;
      if (!count || block + count > Math.ceil(width / 8))
        throw new Error(`Invalid mask run in row ${y}`);
      const size = repeat ? 1 : count;
      if (offset + size > end) throw new Error(`Truncated mask run in row ${y}`);
      for (let i = 0; i < count; i++) {
        const byte = data[offset + (repeat ? 0 : i)]!;
        for (let bit = 0; bit < 8; bit++) {
          const x = (block + i) * 8 + bit;
          if (x < width) pixels[y * width + x] = (byte >> (7 - bit)) & 1;
        }
      }
      offset += size;
      block += count;
    }
  }
  if (offset !== data.length) throw new Error("Trailing mask data");
  return pixels;
}

export interface MaskCoverageRectangle {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** Exact, nonoverlapping screen-space coverage for subsequent intersection
 * with an owner's projected mesh. These rectangles do not establish ownership
 * or height, and must never be treated as recovered 3D geometry by themselves. */
export function recoveryMaskRectangles(mask: Mask): MaskCoverageRectangle[] {
  const pixels = decodeRecoveryMask(mask);
  const [width, height] = mask.box_size;
  const [left, top] = mask.box_top_left;
  if (![left, top].every(Number.isInteger)) throw new Error("Invalid mask origin");
  const rectangles: MaskCoverageRectangle[] = [];
  let previous = new Map<string, MaskCoverageRectangle>();
  for (let y = 0; y < height; y++) {
    const current = new Map<string, MaskCoverageRectangle>();
    let x = 0;
    while (x < width) {
      if (!pixels[y * width + x]) {
        x++;
        continue;
      }
      const start = x++;
      while (x < width && pixels[y * width + x]) x++;
      const key = `${start}:${x}`;
      let rectangle = previous.get(key);
      if (rectangle) rectangle.bottom++;
      else {
        rectangle = { left: left + start, top: top + y, right: left + x, bottom: top + y + 1 };
        rectangles.push(rectangle);
      }
      current.set(key, rectangle);
    }
    previous = current;
  }
  return rectangles;
}
