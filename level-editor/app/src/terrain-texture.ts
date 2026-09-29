import * as THREE from "three";
import { unzlibSync } from "fflate";
import type { GroundRegion } from "@rle/shared";
import tiles from "./terrain-textures/tiles.json" with { type: "json" };

/** Bundled indexed art is decoded synchronously, including for immediate map baking. */
export function terrainTexture(kind: GroundRegion["material"], feather = false) {
  const tile = tiles[kind];
  const palette = atob(tile.palette),
    pixels = unzlibSync(Uint8Array.from(atob(tile.pixelsZlib), (c) => c.charCodeAt(0)));
  const width = feather ? 256 : tile.size;
  const data = new Uint8Array(width * tile.size * 4);
  for (let i = 0; i < width * tile.size; i++) {
    const color = pixels[Math.floor(i / width) * tile.size + (i % width)]! * 3;
    for (let c = 0; c < 3; c++) data[i * 4 + c] = palette.charCodeAt(color + c);
    const u = (i % width) / (width - 1);
    data[i * 4 + 3] = feather
      ? Math.min(255, Math.min(u, 1 - u) * (kind === "water" ? 12800 : 2200))
      : 255;
  }
  const texture = new THREE.DataTexture(data, width, tile.size);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}
