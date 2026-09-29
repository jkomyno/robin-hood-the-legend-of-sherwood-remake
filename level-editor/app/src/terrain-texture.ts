import * as THREE from "three";
import type { GroundRegion } from "@rle/shared";
import tiles from "./terrain-textures/tiles.json" with { type: "json" };

/** Bundled indexed art is decoded synchronously, including for immediate map baking. */
export function terrainTexture(kind: GroundRegion["material"], feather = false) {
  const tile = tiles[kind];
  const palette = atob(tile.palette),
    pixels = atob(tile.pixels);
  const data = new Uint8Array(tile.size * tile.size * 4);
  for (let i = 0; i < pixels.length; i++) {
    const color = pixels.charCodeAt(i) * 3;
    for (let c = 0; c < 3; c++) data[i * 4 + c] = palette.charCodeAt(color + c);
    const u = (i % tile.size) / (tile.size - 1);
    data[i * 4 + 3] = feather
      ? Math.min(255, Math.min(u, 1 - u) * (kind === "water" ? 12800 : 2200))
      : 255;
  }
  const texture = new THREE.DataTexture(data, tile.size, tile.size);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}
