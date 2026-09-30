import assert from "node:assert/strict";
import test from "node:test";
import {
  terrainMaterial,
  terrainMaterials,
  validateCustomTerrainMaterials,
} from "./terrain-materials.ts";

test("catalog preserves every requested design ID and explicit gameplay mapping", () => {
  const expected =
    `grass_short grass_tall grass_lush grass_dry grass_mossy grass_trampled grass_flowers grass_clover grass_leaves grass_stones_small grass_stones_large grass_mud_patches path_dirt path_mud path_puddles path_cart_tracks path_sand path_gravel path_forest_roots path_leaves road_cobblestone road_cobblestone_mossy road_cobblestone_broken path_flagstone water_still water_shallow water_deep water_stone_small_single water_stone_large_single water_stones_small water_stones_large water_white water_white_stone water_reeds water_lily_pads water_ford shore_pebbles shore_mud ground_bare ground_mud ground_sand ground_rocky ground_forest_floor ground_moss field_ploughed field_crops ground_straw floor_paving floor_planks ground_burnt ground_snow ground_swamp`.split(
      " ",
    );
  assert.deepEqual(
    terrainMaterials.map((material) => material.id),
    expected,
  );
  assert.equal(terrainMaterial("water_ford").gameplayMaterial, 5);
  assert.equal(terrainMaterial("shore_pebbles").gameplayMaterial, 2);
  assert.equal(terrainMaterial("floor_planks").gameplayMaterial, 1);
  for (const material of terrainMaterials) assert.match(material.color, /^#[0-9a-f]{6}$/);
});

test("custom materials survive serialization with explicit defaults and overrides", () => {
  const materials = JSON.parse(
    JSON.stringify([
      { id: "custom_red", name: "Red earth", color: "#AB1200" },
      {
        id: "custom_stone",
        name: "Stone",
        color: "#aaaaaa",
        gameplayMaterial: 2,
        textureBase: "paved",
      },
    ]),
  );
  validateCustomTerrainMaterials(materials);
  assert.deepEqual(terrainMaterial("custom_red", materials), {
    id: "custom_red",
    name: "Red earth",
    color: "#AB1200",
    category: "custom",
    gameplayMaterial: 0,
    textureBase: "dirt",
  });
  assert.equal(terrainMaterial("custom_stone", materials).gameplayMaterial, 2);
  assert.equal(terrainMaterial("custom_stone", materials).textureBase, "paved");
});

test("invalid, colliding, and unknown materials fail without silent substitution", () => {
  const valid = { id: "custom_red", name: "Red", color: "#aa0000" };
  for (const value of [
    null,
    {},
    [null],
    [valid, valid],
    [{ ...valid, id: "grass_short" }],
    [{ ...valid, id: "bad id" }],
    [{ ...valid, name: " " }],
    [{ ...valid, color: "red" }],
    [{ ...valid, gameplayMaterial: 9 }],
    [{ ...valid, gameplayMaterial: 0.5 }],
    [{ ...valid, textureBase: "unknown" }],
  ]) {
    assert.throws(() => validateCustomTerrainMaterials(value));
  }
  assert.throws(() => terrainMaterial("missing"), /Unknown terrain material/);
});
