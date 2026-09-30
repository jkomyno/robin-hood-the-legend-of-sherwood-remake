import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { terrainMaterialMixTexture } from "./terrain-material-mix.ts";
test("arbitrary vertex mixtures blend linear colors with source weight kept independent", () => {
  const texture = (id: string) =>
    new THREE.DataTexture(
      new Uint8Array(
        id === "red" ? [255, 0, 0, 255] : id === "blue" ? [0, 0, 255, 255] : [0, 255, 0, 255],
      ),
      1,
      1,
    );
  const result = terrainMaterialMixTexture(
    { red: 0.125, blue: 0.125, green: 0.25, $source: 0.5 },
    texture,
  );
  assert.equal(result.sourceWeight, 0.5);
  const pixel = result.texture.image.data!;
  assert.ok(Math.abs(pixel[0]! - 137) <= 1);
  assert.ok(Math.abs(pixel[1]! - 188) <= 1);
  assert.ok(Math.abs(pixel[2]! - 137) <= 1);
  result.texture.dispose();
});
