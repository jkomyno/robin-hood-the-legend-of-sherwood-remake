import type { Mask, Point } from "../../shared/src/level.ts";
import { decodeRecoveryMask } from "./recover-mask-bitmap.ts";

/** Pixel support only: this does not establish asset ownership or state rules.
 * Extra mesh pixels are expected because recovery clips the mesh to the mask. */
export function maskSurfaceCoverage(mask: Mask, tiles: readonly Mask[]) {
  const original = decodeRecoveryMask(mask);
  const remaining = original.slice();
  const [width, height] = mask.box_size;
  for (const tile of tiles) {
    const pixels = decodeRecoveryMask(tile);
    const dx = tile.box_top_left[0] - mask.box_top_left[0];
    const dy = tile.box_top_left[1] - mask.box_top_left[1];
    for (let y = Math.max(0, -dy); y < Math.min(tile.box_size[1], height - dy); y++)
      for (let x = Math.max(0, -dx); x < Math.min(tile.box_size[0], width - dx); x++)
        if (pixels[y * tile.box_size[0] + x]) remaining[(y + dy) * width + x + dx] = 0;
  }
  let coveredPixels = 0,
    missingPixels = 0,
    interiorMissingPixels = 0;
  let firstMissing: Point | null = null;
  let missingBounds: [number, number, number, number] | null = null;
  for (let i = 0; i < original.length; i++) {
    coveredPixels += original[i]!;
    if (!remaining[i]) continue;
    missingPixels++;
    const x = i % width,
      y = Math.floor(i / width);
    const point: Point = [x + mask.box_top_left[0], y + mask.box_top_left[1]];
    firstMissing ??= point;
    if (!missingBounds) missingBounds = [...point, point[0] + 1, point[1] + 1];
    else {
      missingBounds[0] = Math.min(missingBounds[0], point[0]);
      missingBounds[1] = Math.min(missingBounds[1], point[1]);
      missingBounds[2] = Math.max(missingBounds[2], point[0] + 1);
      missingBounds[3] = Math.max(missingBounds[3], point[1] + 1);
    }
    if (
      x > 0 &&
      y > 0 &&
      x < width - 1 &&
      y < height - 1 &&
      [-1, 0, 1].every((dy) => [-1, 0, 1].every((dx) => original[(y + dy) * width + x + dx]))
    )
      interiorMissingPixels++;
  }
  // Separate disconnected gaps so authoring can repair the actual surfaces,
  // rather than treating their combined bounding rectangle as missing geometry.
  const missingRegions: { pixels: number; bounds: [number, number, number, number] }[] = [];
  for (let seed = 0; seed < remaining.length; seed++) {
    if (!remaining[seed]) continue;
    remaining[seed] = 0;
    const stack = [seed];
    let pixels = 0,
      left = width,
      top = height,
      right = 0,
      bottom = 0;
    while (stack.length) {
      const index = stack.pop()!;
      const x = index % width,
        y = Math.floor(index / width);
      pixels++;
      left = Math.min(left, x);
      top = Math.min(top, y);
      right = Math.max(right, x + 1);
      bottom = Math.max(bottom, y + 1);
      const visit = (neighbor: number) => {
        if (remaining[neighbor]) {
          remaining[neighbor] = 0;
          stack.push(neighbor);
        }
      };
      if (x > 0) visit(index - 1);
      if (x + 1 < width) visit(index + 1);
      if (y > 0) visit(index - width);
      if (y + 1 < height) visit(index + width);
    }
    missingRegions.push({
      pixels,
      bounds: [
        left + mask.box_top_left[0],
        top + mask.box_top_left[1],
        right + mask.box_top_left[0],
        bottom + mask.box_top_left[1],
      ],
    });
  }
  return {
    coveredPixels,
    missingPixels,
    interiorMissingPixels,
    firstMissing,
    missingBounds,
    missingRegions,
  };
}
