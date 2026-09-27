import type { GameplayAssetDescriptor } from "../src/asset-gameplay.ts";
import { IDENTITY_TRANSFORM, type Level3D, type Level3DObject } from "../src/level3d.ts";

export function assetCompilerFixture() {
  const obstacle = {
    points: (
      [
        [40, 40],
        [50, 40],
        [50, 50],
        [40, 50],
      ] as const
    ).map(([x, y]) => ({ x, y, z_bottom: 0, z_top: 30 })),
    projection_area: null,
    solid: true,
    opaque: true,
    mouse: true,
    show_shadow_polygon: false,
    default_material: 0,
    material_indices: [999],
  };
  const hut: GameplayAssetDescriptor = {
    version: 1,
    kind: "projection-mapped-asset",
    id: "hut",
    name: "Two rooms",
    source_map: "unused-provenance",
    model: "hut.glb",
    parts: [
      { node: "building-999", name: "Body", source_obstacle: 999, obstacle_local_game: obstacle },
    ],
    gameplay: {
      version: 1,
      collision: "parts",
      surfaces: [
        {
          id: "west",
          node: "building-999",
          polygon: [
            [0, 0],
            [90, 0],
            [90, 100],
            [0, 100],
          ],
          height: 0,
        },
        {
          id: "east",
          node: "building-999",
          polygon: [
            [110, 0],
            [200, 0],
            [200, 100],
            [110, 100],
          ],
          height: 0,
        },
      ],
      doors: [
        {
          id: "passage",
          node: "building-999",
          polygon: [
            [90, 40],
            [110, 40],
            [110, 60],
            [90, 60],
          ],
          outside: [80, 50, 0],
          inside: [120, 50, 0],
          middle: [100, 50, 0],
          type: 0,
          locked: false,
          unlockable: false,
        },
      ],
      spawns: [],
    },
  };
  const spawn: GameplayAssetDescriptor = {
    version: 1,
    kind: "projection-mapped-asset",
    id: "spawn",
    name: "Spawn",
    source_map: "unused",
    model: "spawn.glb",
    parts: [{ node: "scenery-marker", name: "Marker", scenery: true }],
    gameplay: {
      version: 1,
      collision: "none",
      surfaces: [],
      doors: [],
      spawns: [{ id: "player", node: "scenery-marker", position: [20, 20, 0] }],
    },
  };
  const body: Level3DObject = {
    id: "hut-a-body",
    node: "asset:hut:building-999",
    kind: "building",
    source: { map: "ignored", obstacle: 999 },
    obstacle,
    transform: { ...IDENTITY_TRANSFORM, dx: 300, dy: 300 },
    group: "hut-a",
  };
  const document: Level3D = {
    version: 1,
    map: "Authored fixture",
    sourceMap: "never-read",
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    size: [2000, 2000],
    sceneAssets: [],
    assetSources: [hut, spawn].map((d) => ({
      id: d.id,
      descriptor: `${d.id}.json`,
      model: d.model,
      descriptor_sha256: "0".repeat(64),
      model_sha256: "0".repeat(64),
    })),
    objects: [
      body,
      {
        id: "spawn",
        node: "asset:spawn:scenery-marker",
        kind: "scenery",
        source: { map: "ignored" },
        transform: { ...IDENTITY_TRANSFORM, dx: 300, dy: 300 },
      },
    ],
    groups: [{ id: "hut-a", transform: { ...IDENTITY_TRANSFORM } }],
  };
  return {
    document,
    assets: new Map([
      [hut.id, hut],
      [spawn.id, spawn],
    ]),
    hut,
  };
}

export function slopedAssetCompilerFixture() {
  const fixture = assetCompilerFixture();
  const { hut, assets, document } = fixture;
  hut.gameplay!.doors = [];
  hut.gameplay!.surfaces = [
    {
      id: "ramp",
      node: "building-999",
      polygon: [
        [0, 0],
        [200, 0],
        [200, 100],
        [0, 100],
      ],
      height: [0, 100, 100, 0],
      holes: [
        [
          [70, 60],
          [80, 60],
          [80, 80],
          [70, 80],
        ],
      ],
    },
  ];
  const marker = assets.get("spawn")?.gameplay?.spawns[0];
  if (!marker) throw new Error("Missing fixture spawn");
  marker.position = [20, 20, 10];
  document.map = "Sloped asset fixture";
  return fixture;
}
