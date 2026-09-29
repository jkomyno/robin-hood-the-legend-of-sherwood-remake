import { encode } from "fast-png";
import type { BakePixels } from "./map-compile.ts";

/** Disjoint image regions each contain every combination of their controlling patches.
 * Bit i in the state index means patches[i] is applied. State zero comes from the base bake. */
export interface BakedAppearanceRegion {
  bounds: [number, number, number, number];
  patches: string[];
  states: BakePixels[];
}

export function packageAppearanceRegions(
  prefix: string,
  width: number,
  height: number,
  base: BakePixels,
  regions: readonly BakedAppearanceRegion[],
  transitions: readonly { id: string }[],
): Record<string, Uint8Array> {
  if (!regions.length) return {};
  const files: Record<string, Uint8Array> = {};
  const manifest = regions.map((region, index) => {
    const [x, y, w, h] = region.bounds;
    if (
      !region.bounds.every(Number.isSafeInteger) ||
      x < 0 ||
      y < 0 ||
      w <= 0 ||
      h <= 0 ||
      x + w > width ||
      y + h > height
    )
      throw new Error(`Appearance region ${index} is outside the map`);
    if (
      regions
        .slice(0, index)
        .some(
          ({ bounds: [px, py, pw, ph] }) => x < px + pw && px < x + w && y < py + ph && py < y + h,
        )
    )
      throw new Error("Overlapping appearance regions must share one combined state table");
    if (
      !region.patches.length ||
      region.patches.length > 16 ||
      new Set(region.patches).size !== region.patches.length
    )
      throw new Error("Appearance regions need 1–16 distinct patch bindings");
    const patches = region.patches.map((id) => {
      const patch = transitions.findIndex((transition) => transition.id === id);
      if (patch < 0) throw new Error(`Unresolved appearance transition ${id}`);
      if (patch > 65535) throw new Error("Appearance patch index exceeds the runtime range");
      return patch;
    });
    if (region.states.length !== 2 ** patches.length)
      throw new Error("Appearance region is missing state combinations");
    const states = region.states.map((pixels, state) => {
      if (pixels.color.length !== w * h * 4 || pixels.depth.length !== w * h)
        throw new Error("Appearance state dimensions do not match its region");
      for (let i = 0; i < w * h; i++) {
        if (pixels.color[i * 4 + 3] !== 255)
          throw new Error("Appearance states must contain opaque, fully composited pixels");
        if (state === 0) {
          const offset = (y + Math.floor(i / w)) * width + x + (i % w);
          if (
            pixels.depth[i] !== base.depth[offset] ||
            [0, 1, 2, 3].some((c) => pixels.color[i * 4 + c] !== base.color[offset * 4 + c])
          )
            throw new Error("Initial appearance state does not match the base bake");
        }
      }
      if (state === 0) return null;
      const path = `${prefix}.appearance-${index}-${state}`;
      files[`${path}.png`] = encode({
        width: w,
        height: h,
        data: pixels.color,
        channels: 4,
        depth: 8,
      });
      files[`${path}.depth.png`] = encode({
        width: w,
        height: h,
        data: pixels.depth,
        channels: 1,
        depth: 16,
      });
      return { color: `${path}.png`, depth: `${path}.depth.png` };
    });
    return { bounds: region.bounds, patches, states };
  });
  files[`${prefix}.appearance.json`] = new TextEncoder().encode(
    JSON.stringify({ version: 1, regions: manifest }),
  );
  return files;
}
