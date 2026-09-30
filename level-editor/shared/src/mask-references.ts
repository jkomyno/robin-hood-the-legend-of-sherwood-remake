import type { Mask } from "./level.ts";

const u16 = (value: unknown): value is number =>
  typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 65535;

/** Resolve layer-local references without assuming masks are sorted by layer. */
export function maskReferenceResolver(masks: readonly Pick<Mask, "layer">[]) {
  const layers = new Map<number, number[]>();
  for (const [index, mask] of masks.entries()) {
    if (!u16(mask.layer)) throw new Error(`masks[${index}]: invalid layer`);
    const layer = layers.get(mask.layer) ?? [];
    layer.push(index);
    layers.set(mask.layer, layer);
  }
  return (references: unknown, label = "mask references"): number[] => {
    if (!Array.isArray(references)) throw new Error(`${label}: expected mask reference array`);
    return references.map((reference: unknown, position) => {
      if (
        !reference ||
        typeof reference !== "object" ||
        !("layer" in reference) ||
        !("index" in reference) ||
        !u16(reference.layer) ||
        !u16(reference.index)
      )
        throw new Error(`${label}[${position}]: expected {layer, index} mask reference`);
      const global = layers.get(reference.layer)?.[reference.index];
      if (global === undefined)
        throw new Error(
          `${label}[${position}]: dangling mask reference ${reference.layer}/${reference.index}`,
        );
      return global;
    });
  };
}
