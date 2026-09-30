import type { TerrainGrid } from "@rle/shared";

/** Flatten one selection without changing its footprint or the surrounding ground. */
export function flattenTerrainVertices(grid: TerrainGrid, ids: readonly string[]): TerrainGrid {
  const selected = new Set(ids);
  const vertices = grid.vertices.filter((vertex) => selected.has(vertex.id));
  if (vertices.length !== selected.size)
    throw new Error("Selection contains an unknown terrain vertex");
  if (vertices.length < 2) return grid;
  const height = vertices.reduce((sum, vertex) => sum + vertex.position[2] / vertices.length, 0);
  return {
    ...grid,
    vertices: grid.vertices.map((vertex) =>
      selected.has(vertex.id)
        ? { ...vertex, position: [vertex.position[0], vertex.position[1], height] }
        : vertex,
    ),
  };
}
