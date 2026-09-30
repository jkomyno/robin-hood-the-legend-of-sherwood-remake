/** Encode a baked binary silhouette using native scanline runs (MSB first).
 * Rows have an eight-bit byte count. Callers must tile an incompressible wide
 * silhouette rather than silently truncate its coverage. */
export function encodeMaskBitmap(pixels: Uint8Array, width: number, height: number): number[] {
  if (
    !Number.isInteger(width) ||
    !Number.isInteger(height) ||
    width <= 0 ||
    height <= 0 ||
    width > 32767 ||
    height > 32767 ||
    pixels.length !== width * height
  )
    throw new Error("Invalid mask bitmap dimensions");
  if (pixels.some((pixel) => pixel !== 0 && pixel !== 1))
    throw new Error("Mask pixels must be binary coverage values");
  const result: number[] = [];
  for (let y = 0; y < height; y++) {
    const blocks = new Uint8Array(Math.ceil(width / 8));
    for (let x = 0; x < width; x++) blocks[x >> 3]! |= pixels[y * width + x]! << (7 - (x & 7));
    let end = blocks.length;
    while (end && blocks[end - 1] === 0) end--;
    const row: number[] = [];
    let offset = 0;
    while (offset < end) {
      let repeat = 1;
      while (repeat < 127 && offset + repeat < end && blocks[offset + repeat] === blocks[offset])
        repeat++;
      if (repeat >= 2) {
        row.push(0x80 | repeat, blocks[offset]!);
        offset += repeat;
      } else {
        const begin = offset++;
        while (
          offset < end &&
          offset - begin < 127 &&
          !(offset + 1 < end && blocks[offset] === blocks[offset + 1])
        )
          offset++;
        row.push(offset - begin, ...blocks.subarray(begin, offset));
      }
    }
    if (row.length > 255)
      throw new Error(`Mask row ${y} exceeds 255 encoded bytes; bake narrower tiles`);
    result.push(row.length, ...row);
  }
  return result;
}
