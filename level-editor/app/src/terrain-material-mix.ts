import * as THREE from "three";
/** Mix in linear light, matching shader interpolation; source-image weight remains separate. */
export function terrainMaterialMixTexture(
  mix: Record<string, number>,
  texture: (id: string) => THREE.DataTexture,
) {
  const entries = Object.entries(mix).filter(([id, w]) => id !== "$source" && w > 0),
    sourceWeight = mix.$source ?? 0,
    total = entries.reduce((sum, [, w]) => sum + w, 0);
  if (entries.length === 1) return { texture: texture(entries[0]![0]), sourceWeight, owned: false };
  const samples = entries.map(([id, w]) => ({
    image: texture(id).image,
    weight: total ? w / total : 0,
  }));
  const size = Math.min(256, Math.max(1, ...samples.map((s) => s.image.width))),
    data = new Uint8Array(size * size * 4),
    linear = Array.from({ length: 256 }, (_, i) =>
      i / 255 <= 0.04045 ? i / 255 / 12.92 : Math.pow((i / 255 + 0.055) / 1.055, 2.4),
    );
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const rgb = [0, 0, 0];
      for (const { image, weight } of samples) {
        const i =
          (Math.floor((y * image.height) / size) * image.width +
            Math.floor((x * image.width) / size)) *
          4;
        for (let c = 0; c < 3; c++) rgb[c]! += linear[image.data![i + c]!]! * weight;
      }
      const i = (y * size + x) * 4;
      for (let c = 0; c < 3; c++)
        data[i + c] = Math.round(
          (rgb[c]! <= 0.0031308 ? rgb[c]! * 12.92 : 1.055 * Math.pow(rgb[c]!, 1 / 2.4) - 0.055) *
            255,
        );
      data[i + 3] = 255;
    }
  const result = new THREE.DataTexture(data, size, size);
  result.wrapS = result.wrapT = THREE.RepeatWrapping;
  result.colorSpace = THREE.SRGBColorSpace;
  result.magFilter = THREE.LinearFilter;
  result.minFilter = THREE.LinearMipmapLinearFilter;
  result.generateMipmaps = true;
  result.needsUpdate = true;
  return { texture: result, sourceWeight, owned: true };
}
