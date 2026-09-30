import { createTerrainGrid } from "../src/authored-terrain.ts";
import type { Level3D } from "../src/level3d.ts";

/** A hill, carved river and ford spanning several editable grid cells. */
export function gridTerrainCompilerFixture(): Level3D {
  const terrain = createTerrainGrid([0, 0, 240, 240], 80);
  for (const vertex of terrain.vertices)
    vertex.position[2] = Math.max(0, 40 - Math.abs(vertex.position[0] - 80) / 2);
  return {
    version: 1,
    map: "Grid terrain integration",
    size: [220, 220],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    objects: [],
    groups: [],
    sceneAssets: [],
    terrain,
    splines: [
      {
        id: "river",
        name: "River with ford",
        kind: "river",
        closed: false,
        points: [
          [160, 0, 0],
          [160, 80, 0],
          [160, 160, 0],
          [160, 240, 0],
        ],
        width: 24,
        repeatLength: 80,
        pointMaterials: ["water_still", "water_ford", "water_ford", "water_still"],
      },
    ],
  };
}
