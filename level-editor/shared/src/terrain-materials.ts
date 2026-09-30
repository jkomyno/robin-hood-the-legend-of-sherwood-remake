/** Visual materials do not imply navigation blocking or terrain excavation. */
export type TerrainTextureBase = "grass" | "dirt" | "water" | "paved";
export type TerrainMaterialCategory = "grass" | "path" | "river" | "other" | "custom";

export interface CustomTerrainMaterial {
  id: string;
  name: string;
  /** Six-digit sRGB color, including the leading #. */
  color: string;
  /** Impact/footstep material code, independent of traversability. Defaults to ground (0). */
  gameplayMaterial?: number;
  textureBase?: TerrainTextureBase;
}

export interface TerrainMaterial extends CustomTerrainMaterial {
  category: TerrainMaterialCategory;
  gameplayMaterial: number;
  textureBase: TerrainTextureBase;
}

function presets(
  category: TerrainMaterialCategory,
  textureBase: TerrainTextureBase,
  gameplayMaterial: number,
  entries: readonly (readonly [string, string, string, number?, TerrainTextureBase?])[],
): TerrainMaterial[] {
  return entries.map(([id, name, color, material, base]) => ({
    id,
    name,
    color,
    category,
    gameplayMaterial: material ?? gameplayMaterial,
    textureBase: base ?? textureBase,
  }));
}

/** Named design intentions; tinted base tiles are previews, not finished detail artwork. */
export const terrainMaterials: readonly TerrainMaterial[] = [
  ...presets("grass", "grass", 3, [
    ["grass_short", "Short grass", "#71804a"],
    ["grass_tall", "Tall grass", "#647c3e"],
    ["grass_lush", "Lush grass", "#4f793c"],
    ["grass_dry", "Dry grass", "#a39859"],
    ["grass_mossy", "Mossy grass", "#647344"],
    ["grass_trampled", "Trampled grass", "#82764d"],
    ["grass_flowers", "Grass with flowers", "#809353"],
    ["grass_clover", "Grass with clover", "#5f8546"],
    ["grass_leaves", "Grass with fallen leaves", "#8b7b4b", 4],
    ["grass_stones_small", "Grass with small stones", "#7d825d"],
    ["grass_stones_large", "Grass with large stones", "#777d61"],
    ["grass_mud_patches", "Grass with mud patches", "#766947"],
  ]),
  ...presets("path", "dirt", 0, [
    ["path_dirt", "Dirt path", "#9c835d"],
    ["path_mud", "Muddy path", "#64503b"],
    ["path_puddles", "Path with puddles", "#77725b"],
    ["path_cart_tracks", "Path with cart tracks", "#907650"],
    ["path_sand", "Sandy path", "#c0aa76"],
    ["path_gravel", "Gravel path", "#999383", 2],
    ["path_forest_roots", "Forest path with roots", "#786447", 4],
    ["path_leaves", "Path with fallen leaves", "#957847", 4],
    ["road_cobblestone", "Cobblestone road", "#949185", 2, "paved"],
    ["road_cobblestone_mossy", "Mossy cobblestone", "#7f8868", 2, "paved"],
    ["road_cobblestone_broken", "Broken cobblestone", "#928574", 2, "paved"],
    ["path_flagstone", "Flagstone path", "#aaa193", 2, "paved"],
  ]),
  ...presets("river", "water", 5, [
    ["water_still", "Still water", "#597a7c"],
    ["water_shallow", "Shallow water", "#839e92"],
    ["water_deep", "Deep water", "#365c70"],
    ["water_stone_small_single", "Water with a small stone", "#748b88"],
    ["water_stone_large_single", "Water with a large stone", "#758280"],
    ["water_stones_small", "Water with small stones", "#7e9088"],
    ["water_stones_large", "Water with large stones", "#808984"],
    ["water_white", "Whitewater", "#bbd5d2"],
    ["water_white_stone", "Stone with whitewater", "#a6bab4"],
    ["water_reeds", "Water with reeds", "#6f8969"],
    ["water_lily_pads", "Water with lily pads", "#5b8771"],
    ["water_ford", "Ford (shallow crossing)", "#94a395"],
    ["shore_pebbles", "Pebble shore", "#a8a08a", 2, "dirt"],
    ["shore_mud", "Muddy riverbank", "#77654a", 0, "dirt"],
  ]),
  ...presets("other", "dirt", 0, [
    ["ground_bare", "Bare earth", "#95805e"],
    ["ground_mud", "Mud", "#65513c"],
    ["ground_sand", "Sand", "#c6b47f"],
    ["ground_rocky", "Rocky ground", "#908c7d", 2, "paved"],
    ["ground_forest_floor", "Forest floor (leaves and needles)", "#776244", 4],
    ["ground_moss", "Moss", "#687b42", 3, "grass"],
    ["field_ploughed", "Ploughed field", "#715239"],
    ["field_crops", "Crop field", "#9c9850", 3, "grass"],
    ["ground_straw", "Straw / hay", "#bea665", 4],
    ["floor_paving", "Courtyard paving", "#a49b88", 2, "paved"],
    ["floor_planks", "Wooden planks", "#98744e", 1],
    ["ground_burnt", "Burnt ground / ashes", "#535049"],
    ["ground_snow", "Snow", "#e5e5da", 7],
    ["ground_swamp", "Swamp", "#5a6650", 5, "water"],
  ]),
];

const byId = new Map(terrainMaterials.map((material) => [material.id, material]));
const textureBases = new Set(["grass", "dirt", "water", "paved"]);

export function validateCustomTerrainMaterials(
  value: unknown,
): asserts value is CustomTerrainMaterial[] {
  if (!Array.isArray(value)) throw new Error("Custom terrain materials must be an array");
  const ids = new Set(byId.keys());
  for (const material of value) {
    if (!material || typeof material !== "object" || Array.isArray(material)) {
      throw new Error("Invalid custom terrain material");
    }
    const { id, name, color, gameplayMaterial, textureBase } = material;
    if (typeof id !== "string" || !/^[a-z][a-z0-9_-]*$/.test(id) || ids.has(id)) {
      throw new Error(`Invalid or duplicate terrain material ID: ${String(id)}`);
    }
    if (typeof name !== "string" || !name.trim()) throw new Error(`Material ${id} needs a name`);
    if (typeof color !== "string" || !/^#[0-9a-fA-F]{6}$/.test(color)) {
      throw new Error(`Material ${id} needs a six-digit hex color`);
    }
    if (
      gameplayMaterial !== undefined &&
      (!Number.isInteger(gameplayMaterial) || gameplayMaterial < 0 || gameplayMaterial > 8)
    ) {
      throw new Error(`Material ${id} has an invalid gameplay material`);
    }
    if (textureBase !== undefined && !textureBases.has(textureBase)) {
      throw new Error(`Material ${id} has an invalid texture base`);
    }
    ids.add(id);
  }
}

export function terrainMaterial(
  id: string,
  customMaterials: readonly CustomTerrainMaterial[] = [],
): TerrainMaterial {
  const preset = byId.get(id);
  if (preset) return preset;
  const custom = customMaterials.find((material) => material.id === id);
  if (!custom) throw new Error(`Unknown terrain material: ${id}`);
  validateCustomTerrainMaterials([custom]);
  return {
    ...custom,
    category: "custom",
    gameplayMaterial: custom.gameplayMaterial ?? 0,
    textureBase: custom.textureBase ?? "dirt",
  };
}
