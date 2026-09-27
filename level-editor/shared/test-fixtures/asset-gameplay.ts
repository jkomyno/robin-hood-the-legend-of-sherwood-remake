import type { GameplayAssetDescriptor } from "../src/asset-gameplay.ts";
import { IDENTITY_TRANSFORM, type Level3D, type Level3DObject } from "../src/level3d.ts";

export function lightAssetCompilerFixture() {
  const fixture = interiorAssetCompilerFixture();
  fixture.hut.gameplay!.lights = [
    {
      id: "day-shadow",
      node: "building-999",
      ambiences: 1,
      polygon: [
        [10, 10, 0],
        [30, 10, 0],
        [30, 30, 0],
        [10, 30, 0],
      ],
    },
    {
      id: "night-light",
      node: "building-999",
      ambiences: 2,
      polygon: [
        [60, 10, 0],
        [80, 10, 0],
        [80, 30, 0],
        [60, 30, 0],
      ],
    },
  ];
  return fixture;
}

export function movementTransitionCompilerFixture() {
  const fixture = assetCompilerFixture();
  fixture.hut.gameplay!.movementBlockers = [];
  fixture.hut.gameplay!.movementTransitions = [
    {
      id: "barriers",
      node: "building-999",
      waypoint: [20, 20, 0],
      active: true,
      definitive: false,
      initial: [
        {
          id: "west-barrier",
          node: "building-999",
          height: 0,
          polygon: [
            [45, 0],
            [55, 0],
            [55, 100],
            [45, 100],
          ],
        },
      ],
      applied: [
        {
          id: "east-barrier",
          node: "building-999",
          height: 0,
          polygon: [
            [155, 0],
            [165, 0],
            [165, 100],
            [155, 100],
          ],
        },
      ],
      applyPolygon: [],
      noApplyPolygon: [],
    },
  ];
  return fixture;
}

export function soundAssetCompilerFixture() {
  const fixture = assetCompilerFixture();
  fixture.hut.gameplay!.sounds = [
    {
      id: "stream",
      node: "building-999",
      sample: 17,
      kind: 2,
      active: true,
      delay: [100, 200, 4],
      altitude: 1,
      ambiences: 255,
      spatial: {
        polyline: [
          [10, 20, 5],
          [30, 40, 5],
        ],
        innerDistance: 30,
        outerDistance: 250,
        innerVolume: 70,
        outerVolume: 10,
        noiseCoveringDistance: 60,
      },
    },
    {
      id: "night",
      node: "building-999",
      sample: 18,
      kind: 1,
      active: true,
      altitude: 2,
      ambiences: 0,
    },
  ];
  return fixture;
}

export function materialAssetCompilerFixture() {
  const fixture = assetCompilerFixture();
  fixture.hut.gameplay!.materials = [
    {
      id: "inlay",
      node: "building-999",
      material: 5,
      ground: false,
      obstacles: ["building-999"],
      polygon: [
        [40, 40, 0],
        [50, 40, 0],
        [50, 50, 0],
        [40, 50, 0],
      ],
    },
    {
      id: "paving",
      node: "building-999",
      material: 2,
      ground: true,
      obstacles: [],
      polygon: [
        [10, 10, 0],
        [30, 10, 0],
        [30, 30, 0],
        [10, 30, 0],
      ],
    },
  ];
  return fixture;
}

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
    },
  };
  const marker: GameplayAssetDescriptor = {
    version: 1,
    kind: "projection-mapped-asset",
    id: "marker",
    name: "Scenery marker",
    source_map: "unused",
    model: "marker.glb",
    parts: [{ node: "scenery-marker", name: "Marker", scenery: true }],
    gameplay: {
      version: 1,
      collision: "none",
      surfaces: [],
      doors: [],
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
    assetSources: [hut, marker].map((d) => ({
      id: d.id,
      descriptor: `${d.id}.json`,
      model: d.model,
      descriptor_sha256: "0".repeat(64),
      model_sha256: "0".repeat(64),
    })),
    objects: [
      body,
      {
        id: "marker",
        node: "asset:marker:scenery-marker",
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
      [marker.id, marker],
    ]),
    hut,
  };
}

export function slopedAssetCompilerFixture() {
  const fixture = assetCompilerFixture();
  const { hut, document } = fixture;
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
  document.map = "Sloped asset fixture";
  return fixture;
}

export function clearanceAssetCompilerFixture() {
  const fixture = assetCompilerFixture();
  fixture.document.map = "Movement clearance fixture";
  fixture.hut.gameplay!.movementClearances = [
    {
      id: "pass-through",
      node: "building-999",
      height: 0,
      polygon: [
        [39, 42],
        [51, 42],
        [51, 48],
        [39, 48],
      ],
    },
  ];
  return fixture;
}

export function liftAssetCompilerFixture() {
  const fixture = assetCompilerFixture();
  const { hut } = fixture;
  hut.gameplay!.doors = [];
  const landing = hut.gameplay!.surfaces[1];
  if (!landing) throw new Error("Missing fixture landing");
  landing.height = 100;
  hut.gameplay!.surfaces.push({
    id: "stairs-surface",
    node: "building-999",
    polygon: [
      [90, 0],
      [110, 0],
      [110, 100],
      [90, 100],
    ],
    height: [0, 100, 100, 0],
  });
  hut.gameplay!.lifts = [
    {
      id: "stairs",
      node: "building-999",
      surface: "stairs-surface",
      type: 1,
      direction: [1, 0],
      doors: [
        {
          id: "stairs-low",
          node: "building-999",
          polygon: [],
          type: 5,
          outside: [80, 50, 0],
          inside: [92, 50, 10],
          middle: [90, 50, 0],
          locked: false,
          unlockable: false,
        },
        {
          id: "stairs-high",
          node: "building-999",
          polygon: [],
          type: 4,
          outside: [120, 50, 100],
          inside: [108, 50, 90],
          middle: [110, 50, 100],
          locked: false,
          unlockable: false,
        },
      ],
    },
  ];
  fixture.document.map = "Lift asset fixture";
  return fixture;
}

export function interiorAssetCompilerFixture() {
  const fixture = assetCompilerFixture();
  fixture.hut.gameplay!.interiors = [
    {
      id: "room",
      node: "building-999",
      doors: [20, 80].map((x, i) => ({
        id: `entrance-${i}`,
        node: "building-999",
        type: 1,
        polygon: [
          [x - 5, 90],
          [x + 5, 90],
          [x + 5, 100],
          [x - 5, 100],
        ],
        outside: [x, 80, 0],
        inside: [x, 120, 0],
        middle: [x, 95, 0],
        locked: i === 1,
        unlockable: true,
        lockedCivilians: true,
      })),
    },
  ];
  fixture.document.map = "Interior asset fixture";
  return fixture;
}
