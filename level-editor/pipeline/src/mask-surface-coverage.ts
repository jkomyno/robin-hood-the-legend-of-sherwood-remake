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
  return { coveredPixels, missingPixels, interiorMissingPixels, firstMissing, missingBounds };
}
