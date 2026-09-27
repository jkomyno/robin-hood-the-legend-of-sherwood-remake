/** One-time source audit; deliberately independent of the map compiler. */
import fs from "node:fs/promises";
import { parseArgs } from "node:util";
import type { ProtoLevel } from "../../shared/src/level.ts";
import { decodeRecoveryMask, recoveryMaskRectangles } from "./recover-mask-bitmap.ts";
import { maskBoundaryPolyline } from "../../shared/src/compile-mask-geometry.ts";

const { positionals } = parseArgs({ allowPositionals: true });
if (!positionals.length) throw new Error("Usage: audit-mask-bitmaps.ts <level.rhp.json> [...]");
let failed = false;
for (const source of positionals) {
  const level: ProtoLevel = JSON.parse(await fs.readFile(source, "utf8"));
  let exact = 0,
    coveredPixels = 0,
    rectangles = 0,
    obstacleLinked = 0;
  const errors: { index: number; error: string }[] = [];
  let exactBoundaries = 0;
  for (const [index, mask] of level.masks.entries()) {
    try {
      const pixels = decodeRecoveryMask(mask);
      const coverage = recoveryMaskRectangles(mask);
      const reconstructed = new Uint8Array(pixels.length);
      const [left, top] = mask.box_top_left;
      const [width] = mask.box_size;
      for (const rectangle of coverage)
        for (let y = rectangle.top; y < rectangle.bottom; y++)
          for (let x = rectangle.left; x < rectangle.right; x++) {
            const i = (y - top) * width + x - left;
            if (reconstructed[i]) throw new Error("Overlapping recovered rectangles");
            reconstructed[i] = 1;
          }
      if (!pixels.every((pixel, i) => pixel === reconstructed[i]))
        throw new Error("Recovered coverage differs from source bitmap");
      for (const boundary of [mask.character_polyline, mask.projectile_polyline]) {
        if (!boundary?.length) continue;
        if (JSON.stringify(maskBoundaryPolyline(boundary, false)) !== JSON.stringify(boundary))
          throw new Error("Open boundary differs from source polyline");
        exactBoundaries++;
      }
      coveredPixels += pixels.reduce((sum, pixel) => sum + pixel, 0);
      rectangles += coverage.length;
      obstacleLinked += Number(mask.obstacle_indices.length > 0);
      exact++;
    } catch (error) {
      errors.push({ index, error: String(error) });
    }
  }
  failed ||= errors.length > 0;
  console.log(
    JSON.stringify({
      source,
      masks: level.masks.length,
      exact,
      coveredPixels,
      rectangles,
      exactBoundaries,
      obstacleLinked,
      errors,
    }),
  );
}
if (failed) process.exitCode = 1;
