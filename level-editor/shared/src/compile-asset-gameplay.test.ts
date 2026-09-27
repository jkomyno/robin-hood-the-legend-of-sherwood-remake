import test from "node:test";
import assert from "node:assert/strict";
import { compileAssetGameplay } from "./compile-asset-gameplay.ts";
import { validateAssetGameplay } from "./asset-gameplay.ts";
import { IDENTITY_TRANSFORM } from "./level3d.ts";
import {
  assetCompilerFixture,
  slopedAssetCompilerFixture,
  liftAssetCompilerFixture,
  interiorAssetCompilerFixture,
  soundAssetCompilerFixture,
  movementTransitionCompilerFixture,
  sightTransitionCompilerFixture,
  lightAssetCompilerFixture,
  jumpAssetCompilerFixture,
  compoundLiftCompilerFixture,
  multiPlaneRegionCompilerFixture,
  crossAssetJumpCompilerFixture,
  doorTransitionCompilerFixture,
} from "../test-fixtures/asset-gameplay.ts";

import { heightPlane, planeHeight } from "./gameplay-plane.ts";

const bounds: [number, number, number, number] = [0, 0, 2000, 2000];
test("door-only transitions resolve native interior-first indices independently for each placement", () => {
  const { document, assets, hut } = doorTransitionCompilerFixture();
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    compiled.movement_transitions!.map((t) => t.door_links),
    [
      { mode: "trigger-transition", indices: [2] },
      { mode: "swap-rights", indices: [0, 1] },
    ],
  );
  const part = structuredClone(document.objects.find((p) => p.group === "hut-a")!);
  part.id = "copy";
  part.group = "hut-b";
  part.transform.dx += 300;
  document.objects.push(part);
  document.groups.push({
    ...structuredClone(document.groups.find((g) => g.id === "hut-a")!),
    id: "hut-b",
  });
  const duplicate = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    duplicate.movement_transitions!.map((t) => t.door_links),
    [
      { mode: "trigger-transition", indices: [4] },
      { mode: "swap-rights", indices: [0, 1] },
      { mode: "trigger-transition", indices: [5] },
      { mode: "swap-rights", indices: [2, 3] },
    ],
  );
  hut.gameplay!.movementTransitions![0]!.doorLinks!.ids = ["missing"];
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /missing ordinary\/interior door/,
  );
  hut.gameplay!.movementTransitions![0]!.doorLinks!.ids = ["passage"];
  hut.gameplay!.movementTransitions![1]!.doorLinks = {
    mode: "trigger-transition",
    ids: ["passage"],
  };
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /triggers multiple transitions/,
  );
});
test("sight transitions rebuild local references and reject ambiguous obstacle control", () => {
  const { document, assets, hut } = sightTransitionCompilerFixture();
  const geometry = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(geometry.movement_transitions![0]!.initial_sight, [0]);
  assert.deepEqual(geometry.movement_transitions![0]!.applied_sight, [1]);
  const transition = hut.gameplay!.movementTransitions![0]!;
  transition.initial = [];
  transition.applied = [];
  assert.deepEqual(
    compileAssetGameplay(document, assets, bounds).movement_transitions![0]!.motion_changes,
    [],
  );
  transition.appliedSight = ["building-999"];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /multiply controlled/);
  transition.appliedSight = ["missing"];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /sight obstacle/);
  transition.appliedSight = ["open-barrier"];
  delete hut.gameplay!.movementBlockers;
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /explicit movement blockers/);
});
test("hidden mesh frames retain explicit gameplay and only referenced sight geometry", () => {
  const { document, assets, hut } = sightTransitionCompilerFixture();
  const part = document.objects.find((p) => p.node.endsWith(":building-999"))!;
  const visible = structuredClone(part);
  visible.id = "visible-anchor";
  visible.node = visible.node.replace("building-999", "anchor");
  hut.parts.push({ node: "anchor", name: "Visible frame", scenery: true });
  document.objects.push(visible);
  part.hidden = true;
  let geometry = compileAssetGameplay(document, assets, bounds);
  assert.equal(geometry.doors.length, 1);
  assert.equal(geometry.sight_obstacles.length, 2);
  delete hut.gameplay!.movementTransitions![0]!.initialSight;
  geometry = compileAssetGameplay(document, assets, bounds);
  assert.equal(geometry.sight_obstacles.length, 1);
  assert.deepEqual(geometry.movement_transitions![0]!.applied_sight, [0]);
});
for (const kind of ["part", "volume"] as const)
  test(`selected permanent ${kind} collision retains its clearances independently of changing sight`, () => {
    const { document, assets, hut } = sightTransitionCompilerFixture();
    const gameplay = hut.gameplay!;
    delete gameplay.movementBlockers;
    const fixed = structuredClone(hut.parts[0]!.obstacle_local_game!);
    fixed.points = fixed.points.map((p) => ({ ...p, y: p.y + 30 }));
    let ref: string;
    if (kind === "part") {
      ref = "building-998";
      hut.parts.push({
        node: ref,
        name: "Permanent wall",
        source_obstacle: 998,
        obstacle_local_game: fixed,
      });
      const placed = structuredClone(document.objects.find((p) => p.group === "hut-a")!);
      placed.id = "fixed-wall";
      placed.node = `asset:hut:${ref}`;
      placed.obstacle = fixed;
      document.objects.push(placed);
    } else {
      ref = "fixed-wall";
      const { projection_area: _projection, material_indices: _materials, ...shape } = fixed;
      gameplay.volumes!.push({ id: ref, node: "building-999", shape });
    }
    gameplay.movementSolids = [ref];
    gameplay.movementClearances = [
      {
        id: "opening",
        node: "building-999",
        height: 0,
        polygon: [
          [40, 70],
          [45, 70],
          [45, 80],
          [40, 80],
        ],
      },
    ];
    const compiled = compileAssetGameplay(document, assets, bounds);
    const permanent = compiled.motion_data.layers.flatMap((layer) =>
      layer.flatMap((area) => area.obstacles.filter((o) => o.state_id === 0)),
    );
    assert.equal(permanent.length, 1);
    assert.deepEqual(permanent[0]!.polygon.points.map((p) => p.join(",")).sort(), [
      "345,370",
      "345,380",
      "350,370",
      "350,380",
    ]);
    assert.equal(compiled.sight_obstacles.length, 3);
    assert.equal(compiled.movement_transitions!.length, 1);
    for (const part of document.objects) part.transform.dx += 100;
    const moved = compileAssetGameplay(document, assets, bounds);
    const after = moved.motion_data.layers.flatMap((layer) =>
      layer.flatMap((area) => area.obstacles.filter((o) => o.state_id === 0)),
    );
    assert.deepEqual(
      after[0]!.polygon.points,
      permanent[0]!.polygon.points.map(([x, y]) => [x + 100, y]),
    );
    gameplay.movementSolids = ["absent"];
    assert.throws(
      () => compileAssetGameplay(document, assets, bounds),
      /invalid permanent movement solid/,
    );
    gameplay.movementSolids = [ref, ref];
    assert.throws(
      () => compileAssetGameplay(document, assets, bounds),
      /invalid permanent movement solids/,
    );
  });
test("duplicated sight transitions control only their own transformed obstacles", () => {
  const { document, assets } = sightTransitionCompilerFixture();
  const part = document.objects.find((p) => p.group)!;
  document.groups.push({
    id: "state-copy",
    transform: { ...IDENTITY_TRANSFORM, dx: 1000, rot_deg: 90 },
  });
  document.objects.push({ ...structuredClone(part), id: "state-copy-part", group: "state-copy" });
  const geometry = compileAssetGameplay(document, assets, bounds);
  const [first, second] = geometry.movement_transitions!;
  assert.equal(geometry.movement_transitions!.length, 2);
  assert.deepEqual(first!.initial_sight, [0]);
  assert.deepEqual(second!.initial_sight, [2]);
  assert.deepEqual(second!.applied_sight, [3]);
  assert.notDeepEqual(geometry.sight_obstacles[0]!.points, geometry.sight_obstacles[2]!.points);
});
test("cross-asset jump edges assemble equivalent native links and detect broken placement", () => {
  const { document, assets } = crossAssetJumpCompilerFixture();
  const whole = jumpAssetCompilerFixture();
  assert.deepEqual(
    compileAssetGameplay(document, assets, bounds),
    compileAssetGameplay(whole.document, whole.assets, bounds),
  );
  document.groups.find((g) => g.id === "jump-upper")!.transform.dx = 20;
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /exactly one complementary edge/,
  );
  document.groups.find((g) => g.id === "jump-upper")!.transform.dx = 0;
  for (const group of document.groups.slice())
    document.groups.push({
      id: `${group.id}-copy`,
      transform: { ...IDENTITY_TRANSFORM, dx: 1000, dy: 100, rot_deg: 90 },
    });
  for (const part of [...document.objects].filter((p) => p.group))
    document.objects.push({
      ...structuredClone(part),
      id: `${part.id}-copy`,
      group: `${part.group}-copy`,
    });
  const copies = compileAssetGameplay(document, assets, bounds);
  assert.equal(copies.jump_line_pairs!.length, 2);
  assert.equal(copies.jump_zones!.length, 4);
  assert.notEqual(
    copies.jump_line_pairs![0]!.line1.jump_zone_index,
    copies.jump_line_pairs![1]!.line1.jump_zone_index,
  );
});
test("non-rendering asset volumes preserve collision and sight without a mesh part", () => {
  const { hut, document, assets } = assetCompilerFixture();
  const expected = compileAssetGameplay(document, assets, bounds);
  const {
    projection_area: _projection,
    material_indices: _materials,
    ...shape
  } = hut.parts[0]!.obstacle_local_game!;
  hut.gameplay!.collision = "none";
  hut.gameplay!.volumes = [
    { id: "invisible-wall", node: "building-999", shape: structuredClone(shape) },
  ];
  const normalized = (value: unknown) =>
    JSON.parse(
      JSON.stringify(value, (_, v) => (typeof v === "number" ? Math.round(v * 1e8) / 1e8 : v)),
    );
  assert.deepEqual(
    normalized(compileAssetGameplay(document, assets, bounds)),
    normalized(expected),
  );
  document.groups[0]!.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.equal(
    moved.sight_obstacles[0]!.points[0]!.x,
    expected.sight_obstacles[0]!.points[0]!.x + 100,
  );
  hut.gameplay!.materials = [
    {
      id: "wall-material",
      node: "building-999",
      material: 2,
      ground: false,
      obstacles: ["invisible-wall"],
      polygon: [
        [40, 40, 0],
        [50, 40, 0],
        [50, 50, 0],
        [40, 50, 0],
      ],
    },
  ];
  assert.deepEqual(
    compileAssetGameplay(document, assets, bounds).sight_obstacles[0]!.material_indices,
    [0],
  );
  hut.gameplay!.volumes[0]!.node = "missing";
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /unknown gameplay node/);
  hut.gameplay!.volumes[0]!.node = "building-999";
  Object.assign(hut.gameplay!.volumes[0]!.shape, { projection_area: [123, 1] });
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /invalid gameplay volume/);
});
test("ordinary local navigation regions join height planes without lift behavior", () => {
  const { document, assets, hut } = multiPlaneRegionCompilerFixture();
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.equal(compiled.motion_data.layers.flat().length, 1);
  const projections = compiled.sight_obstacles.filter((s) => Array.isArray(s.projection_area));
  assert.equal(projections.length, 2);
  assert.deepEqual(projections[0]!.projection_area, projections[1]!.projection_area);
  assert.equal(compiled.lifts?.length ?? 0, 0);
  hut.gameplay!.surfaces[1]!.navigationRegion = "separate";
  assert.equal(compileAssetGameplay(document, assets, bounds).motion_data.layers.flat().length, 2);
});

test("multi-plane regions retain independent sectors after rotation and duplication", () => {
  const { document, assets } = multiPlaneRegionCompilerFixture();
  const part = document.objects.find((p) => p.group)!;
  document.groups.push({
    id: "roof-copy",
    transform: { ...IDENTITY_TRANSFORM, dx: 1000, rot_deg: 90 },
  });
  document.objects.push({ ...structuredClone(part), id: "roof-copy-part", group: "roof-copy" });
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.equal(compiled.motion_data.layers.flat().length, 2);
  const regions = new Map<string, number>();
  for (const surface of compiled.sight_obstacles) {
    const key = JSON.stringify(surface.projection_area);
    regions.set(key, (regions.get(key) ?? 0) + 1);
  }
  assert.deepEqual([...regions.values()], [2, 2]);
});

test("joined lift assets retain multiple height planes in one traversal sector", () => {
  const { document, assets, upper } = compoundLiftCompilerFixture();
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.equal(compiled.lifts!.length, 1);
  const lift = compiled.lifts![0]!;
  assert.equal(lift.doors.length, 2);
  assert.equal(compiled.motion_data.layers.at(-1)!.length, 1);
  const projections = compiled.sight_obstacles.filter(
    (s) => Array.isArray(s.projection_area) && s.projection_area[0] === lift.motion_area_index,
  );
  assert.equal(projections.length, 2);
  assert.deepEqual(
    lift.doors.map((d) => d.sector_in),
    [lift.motion_area_index, lift.motion_area_index],
  );
  document.groups.find((g) => g.id === "upper")!.transform.dx = 10;
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /join must match/);
  document.groups.find((g) => g.id === "upper")!.transform.dx = 0;
  upper.gameplay!.lifts![0]!.type = 2;
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /type and direction disagree/,
  );
});
test("compound lifts rotate and duplicate with independent geometric joins", () => {
  const { document, assets } = compoundLiftCompilerFixture();
  const groups = [...document.groups];
  const parts = [...document.objects];
  for (const group of groups) {
    document.groups.push({
      id: `${group.id}-copy`,
      transform: { ...IDENTITY_TRANSFORM, dx: 1000, dy: 100, rot_deg: 90 },
    });
  }
  for (const part of parts.filter((p) => p.group)) {
    document.objects.push({
      ...structuredClone(part),
      id: `${part.id}-copy`,
      group: `${part.group}-copy`,
    });
  }
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.equal(compiled.lifts!.length, 2);
  assert.notEqual(compiled.lifts![0]!.motion_area_index, compiled.lifts![1]!.motion_area_index);
  assert.equal(compiled.lifts![1]!.doors.length, 2);
  assert.notEqual(compiled.lifts![0]!.direction, compiled.lifts![1]!.direction);
});

test("asset-local navigation regions preserve gates between touching coplanar rooms", () => {
  const { hut, document, assets } = assetCompilerFixture();
  const [west, east] = hut.gameplay!.surfaces;
  west!.polygon = [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100],
  ];
  east!.polygon = [
    [100, 0],
    [200, 0],
    [200, 100],
    [100, 100],
  ];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /distinct motion areas/);
  west!.navigationRegion = "west";
  east!.navigationRegion = "east";
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.equal(compiled.motion_data.layers[0]!.length, 2);
  assert.notEqual(compiled.doors[0]!.sector_in, compiled.doors[0]!.sector_out);
  east!.navigationRegion = "west";
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /distinct motion areas/);
  east!.navigationRegion = "";
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /navigation regions/);
});

test("navigation region labels belong to each placement independently", () => {
  const { hut, document, assets } = assetCompilerFixture();
  hut.gameplay!.doors = [];
  hut.gameplay!.surfaces = [hut.gameplay!.surfaces[0]!];
  const surface = hut.gameplay!.surfaces[0]!;
  surface.navigationRegion = "room";
  const copy = structuredClone(document.objects[0]!);
  copy.id = "copy";
  copy.group = "copy";
  document.objects.push(copy);
  document.groups.push({ id: "copy", transform: { ...IDENTITY_TRANSFORM, dx: 90 } });
  assert.equal(compileAssetGameplay(document, assets, bounds).motion_data.layers[0]!.length, 2);
  delete surface.navigationRegion;
  assert.equal(compileAssetGameplay(document, assets, bounds).motion_data.layers[0]!.length, 1);
});

test("jump pairs rebuild crossed destination links and preserve height after duplication", () => {
  const { hut, document, assets } = jumpAssetCompilerFixture();
  const first = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    first.jump_zones!.map((z) => [z.sector, z.layer]),
    [
      [0, 0],
      [2, 1],
    ],
  );
  assert.deepEqual(first.jump_line_pairs![0], {
    line1: { point_a: [385, 330, 0], point_b: [385, 370, 0], jump_zone_index: 1 },
    line2: { point_a: [415, 270, 100], point_b: [415, 230, 100], jump_zone_index: 0 },
    jump_long: true,
  });
  const body = structuredClone(document.objects.find((p) => p.group === "hut-a")!);
  body.id = "jump-copy";
  body.group = "jump-copy";
  document.objects.push(body);
  document.groups.push({
    id: "jump-copy",
    transform: { ...IDENTITY_TRANSFORM, dx: 700, dy: 500, rot_deg: 90 },
  });
  const copied = compileAssetGameplay(document, assets, bounds);
  assert.equal(copied.jump_zones!.length, 4);
  assert.equal(copied.jump_line_pairs![1]!.line1.jump_zone_index, 3);
  assert.equal(copied.jump_line_pairs![1]!.line2.jump_zone_index, 2);
  assert.notDeepEqual(
    copied.jump_line_pairs![1]!.line1.point_a,
    first.jump_line_pairs![0]!.line1.point_a,
  );
  hut.gameplay!.jumpPairs![0]!.edges[0].a[2] = 20;
  assert.equal(
    compileAssetGameplay(document, assets, bounds).jump_line_pairs![0]!.line1.point_a[2],
    20,
  );
});
test("jump metadata rejects orphan zones, missing links and collapsed edges", () => {
  const { hut, document, assets } = jumpAssetCompilerFixture();
  const pair = hut.gameplay!.jumpPairs![0]!;
  pair.edges[0].zone = "missing";
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /missing zone/);
  pair.edges[0].zone = "low-zone";
  pair.edges[0].b = [...pair.edges[0].a];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /collapses/);
  hut.gameplay!.jumpPairs = [];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /no paired edge/);
});
test("light regions follow placement and preserve ambience without shifting interior links", () => {
  const { hut, document, assets } = lightAssetCompilerFixture();
  const first = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    first.light_sectors?.map((l) => [l.layer, l.ambience]),
    [
      [0, 1],
      [0, 2],
    ],
  );
  assert.deepEqual(first.light_sectors![0]!.polygon.points[0], [310, 310]);
  document.groups[0]!.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(moved.light_sectors![0]!.polygon.points[0], [410, 310]);
  assert.equal(
    moved.buildings![0]!.Building.doors[0]!.sector_in,
    first.buildings![0]!.Building.doors[0]!.sector_in,
  );
  hut.gameplay!.lights![0]!.ambiences = -1;
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /invalid light region/);
});

test("light receiving planes resolve after elevation and reject absent or nonplanar surfaces", () => {
  const { hut, document, assets } = slopedAssetCompilerFixture();
  hut.gameplay!.lights = [
    {
      id: "ramp-shadow",
      node: "building-999",
      ambiences: 0xffffffff,
      polygon: [
        [10, 10, 5],
        [30, 10, 15],
        [30, 30, 15],
        [10, 30, 5],
      ],
    },
  ];
  const first = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(first.light_sectors![0]!.polygon.points[0], [310, 305]);
  const light = hut.gameplay!.lights[0]!;
  light.polygon = light.polygon.map(([x, y, z]) => [x, y, z + 100]);
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /receiving layer/);
  light.polygon[0]![2] += 1;
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /must be planar/);
});

test("movement transitions receive fresh bindings across separate areas and duplicated assets", () => {
  const { document, assets } = movementTransitionCompilerFixture();
  const first = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(first.movement_transitions![0]!.motion_changes, [
    { layer: 0, sector: 0, changing_obstacle: 0 },
    { layer: 0, sector: 2, changing_obstacle: 0 },
  ]);
  assert.deepEqual(
    first.motion_data.layers[0]!.map((a) => a.obstacles.map((o) => o.state_id)),
    [[1], [2]],
  );
  const body = structuredClone(document.objects.find((p) => p.group === "hut-a")!);
  body.id = "hut-b-body";
  body.group = "hut-b";
  document.objects.push(body);
  document.groups.push({
    ...structuredClone(document.groups.find((g) => g.id === "hut-a")!),
    id: "hut-b",
  });
  const doubled = compileAssetGameplay(document, assets, bounds);
  assert.equal(doubled.movement_transitions!.length, 2);
  assert.deepEqual(
    doubled.motion_data.layers[0]!.map((a) => a.obstacles.map((o) => o.state_id)),
    [
      [1, 4],
      [2, 8],
    ],
  );
  for (const p of document.objects) p.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(moved.movement_transitions![0]!.waypoint, [420, 320]);
  assert.equal(moved.motion_data.layers[0]![0]!.obstacles[0]!.polygon.points[0]![0], 445);
});
test("transition reference points may be blocked but must still resolve to a surface", () => {
  const { document, assets, hut } = movementTransitionCompilerFixture();
  hut.gameplay!.movementBlockers = [
    {
      id: "fixed-wall",
      node: "building-999",
      height: 0,
      polygon: [
        [10, 10],
        [30, 10],
        [30, 30],
        [10, 30],
      ],
    },
  ];
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(compiled.movement_transitions![0]!.waypoint, [320, 320]);
  const transition = hut.gameplay!.movementTransitions![0]!;
  const door = hut.gameplay!.doors[0]!;
  const outside = door.outside;
  door.outside = [...transition.waypoint];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /unblocked walkable surface/);
  door.outside = outside;
  transition.waypoint = [20, 20, 100];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /waypoint must resolve/);
});
test("sound geometry follows placement while acoustic categories and falloff remain intact", () => {
  const { document, assets, hut } = soundAssetCompilerFixture();
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(compiled.sound_sources![0]!.polyline, [
    [310, 315],
    [330, 335],
  ]);
  assert.equal(compiled.sound_sources![0]!.altitude, 1);
  assert.deepEqual(compiled.sound_sources![0]!.delayed_params, [100, 200, 4]);
  assert.equal(compiled.sound_sources![1]!.global, true);
  assert.equal(compiled.sound_sources![1]!.polyline, null);
  for (const p of document.objects) p.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(moved.sound_sources![0]!.polyline, [
    [410, 315],
    [430, 335],
  ]);
  assert.equal(moved.sound_sources![0]!.noise_covering_distance, 60);
  hut.gameplay!.sounds![0]!.delay![2] = 65535;
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /invalid sound delay/);
  hut.gameplay!.sounds![0]!.delay![2] = 4;
  hut.gameplay!.sounds![0]!.spatial!.innerVolume = 101;
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /invalid sound geometry/);
  hut.gameplay!.sounds![0]!.spatial!.innerVolume = 70;
  hut.parts.push({ node: "absent", name: "Absent emitter", scenery: true });
  hut.gameplay!.sounds![1]!.node = "absent";
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /absent is hidden or missing/,
  );
});
test("terrain owns map defaults and conflicting terrain definitions fail", () => {
  const { document, assets, hut } = assetCompilerFixture();
  const terrain = {
    ...structuredClone(hut),
    id: "terrain",
    editor_usage: "map-background" as const,
    parts: [],
    gameplay: {
      version: 1 as const,
      collision: "none" as const,
      surfaces: [],
      doors: [],
      environment: { forest: true, defaultMaterial: 4 },
    },
  };
  assets.set(terrain.id, terrain);
  const source = {
    id: terrain.id,
    role: "ground" as const,
    model: "terrain.glb",
    model_sha256: "0".repeat(64),
    resources: [],
  };
  document.sceneAssets.push(source);
  assert.deepEqual(compileAssetGameplay(document, assets, bounds).map_settings, {
    forest_level: true,
    default_material: 4,
  });
  const other = structuredClone(terrain);
  other.id = "other-terrain";
  other.gameplay.environment.forest = false;
  assets.set(other.id, other);
  document.sceneAssets.push({ ...source, id: other.id });
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /Terrain assets disagree/);
  hut.gameplay!.environment = { forest: false, defaultMaterial: 0 };
  assert.throws(() => validateAssetGameplay(hut.gameplay, hut), /invalid terrain environment/);
});
test("material regions follow placement and preserve separate ground and obstacle lookups", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.materials = [
    {
      id: "stone-inlay",
      node: "building-999",
      material: 2,
      ground: false,
      obstacles: ["building-999"],
      polygon: [
        [40, 40, 10],
        [50, 40, 10],
        [50, 50, 10],
        [40, 50, 10],
      ],
    },
    {
      id: "water",
      node: "building-999",
      material: 5,
      ground: true,
      obstacles: [],
      polygon: [
        [10, 10, 0],
        [20, 10, 0],
        [20, 20, 0],
        [10, 20, 0],
      ],
    },
  ];
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(compiled.sight_material_indices, [1]);
  assert.deepEqual(compiled.sight_obstacles[0]!.material_indices, [0]);
  assert.deepEqual(compiled.material_sectors![0]!.polygon.points[0], [340, 330]);
  for (const p of document.objects) p.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(moved.material_sectors![0]!.polygon.points[0], [440, 330]);
  hut.gameplay!.materials[0]!.obstacles = ["missing"];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /invalid material region/);
});

test("material constructors are included in regenerated interior identities", () => {
  const { document, assets } = interiorAssetCompilerFixture();
  const descriptor = [...assets.values()].find((a) => a.gameplay?.interiors?.length)!;
  const before = compileAssetGameplay(document, assets, bounds);
  descriptor.gameplay!.materials = [
    {
      id: "floor",
      node: descriptor.parts[0]!.node,
      material: 2,
      ground: true,
      obstacles: [],
      polygon: [
        [0, 0, 0],
        [10, 0, 0],
        [10, 10, 0],
        [0, 10, 0],
      ],
    },
  ];
  const after = compileAssetGameplay(document, assets, bounds);
  assert.equal(
    after.buildings![0]!.Building.doors[0]!.sector_in,
    before.buildings![0]!.Building.doors[0]!.sector_in + 1,
  );
});
test("movement clearances follow their owner and cannot erase another asset's collision", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.movementClearances = [
    {
      id: "opening",
      node: "building-999",
      polygon: [
        [39, 39],
        [51, 39],
        [51, 51],
        [39, 51],
      ],
      height: 0,
    },
  ];
  const clear = compileAssetGameplay(document, assets, bounds);
  assert.equal(clear.motion_data.layers[0]![0]!.obstacles.length, 0);
  assert.equal(clear.sight_obstacles[0]!.solid, true);
  for (const p of document.objects) p.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.equal(moved.motion_data.layers[0]![0]!.obstacles.length, 0);
  assert.equal(moved.sight_obstacles[0]!.points[0]!.x, 440);
  const other = assets.get("marker")!;
  other.gameplay!.collision = "parts";
  other.parts[0]!.obstacle_local_game = structuredClone(hut.parts[0]!.obstacle_local_game!);
  assert.equal(
    compileAssetGameplay(document, assets, bounds).motion_data.layers[0]![0]!.obstacles.length,
    1,
  );
  other.gameplay!.collision = "none";
  hut.gameplay!.movementClearances[0]!.height = 1;
  assert.equal(
    compileAssetGameplay(document, assets, bounds).motion_data.layers[0]![0]!.obstacles.length,
    1,
  );
});

test("an enclosed clearance retains a walkable island inside derived collision", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.movementClearances = [
    {
      id: "island",
      node: "building-999",
      polygon: [
        [42, 42],
        [48, 42],
        [48, 48],
        [42, 48],
      ],
      height: 0,
    },
  ];
  const result = compileAssetGameplay(document, assets, bounds);
  assert.equal(result.motion_data.layers[0]!.length, 3);
  assert.ok(
    result.motion_data.layers[0]!.some((a) =>
      a.polygon.points.every(([x, y]) => x >= 342 && x <= 348 && y >= 342 && y <= 348),
    ),
  );
});
test("map assets reject mission spawns rather than silently dropping them", () => {
  const { document, assets, hut } = assetCompilerFixture();
  Object.assign(hut.gameplay!, {
    spawns: [{ id: "player", node: "building-999", position: [20, 20, 0] }],
  });
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /spawns belong to missions/);
});
test("authored subpixel surfaces remain errors rather than being silently omitted", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.surfaces[0]!.polygon = [
    [0, 0],
    [0.1, 0],
    [0.1, 100],
    [0, 100],
  ];
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /collapses after coordinate quantization/,
  );
});

test("authored movement contours follow an asset independently of sight and terrain", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.doors = [];
  hut.gameplay!.surfaces = [];
  hut.gameplay!.movementBlockers = [
    {
      id: "clearance",
      node: "building-999",
      polygon: [
        [35, 35],
        [55, 35],
        [55, 55],
        [35, 55],
      ],
      height: 0,
    },
  ];
  const marker = assets.get("marker")!.gameplay!;
  marker.surfaces = [
    {
      id: "terrain",
      node: "scenery-marker",
      polygon: [
        [0, 0],
        [300, 0],
        [300, 200],
        [0, 200],
      ],
      height: 0,
    },
  ];
  const before = compileAssetGameplay(document, assets, bounds);
  const sortedPoints = (points: [number, number][]) =>
    [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  assert.deepEqual(sortedPoints(before.motion_data.layers[0]![0]!.obstacles[0]!.polygon.points), [
    [335, 335],
    [335, 355],
    [355, 335],
    [355, 355],
  ]);
  assert.equal(before.sight_obstacles[0]!.points[0]!.x, 340);
  document.objects[0]!.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    moved.motion_data.layers[0]![0]!.polygon,
    before.motion_data.layers[0]![0]!.polygon,
  );
  assert.deepEqual(sortedPoints(moved.motion_data.layers[0]![0]!.obstacles[0]!.polygon.points), [
    [435, 335],
    [435, 355],
    [455, 335],
    [455, 355],
  ]);
  // A plane-specific blocker no longer blocks ground when raised above it.
  document.objects[0]!.transform.dz = 100;
  assert.equal(
    compileAssetGameplay(document, assets, bounds).motion_data.layers[0]![0]!.obstacles.length,
    0,
  );
});

test("asset-only compilation constructs motion areas, fresh references and doors", () => {
  const { document, assets } = assetCompilerFixture();
  const result = compileAssetGameplay(document, assets, bounds);
  assert.equal(result.motion_data.layers.length, 2);
  assert.equal(result.motion_data.layers[0]!.length, 2);
  assert.deepEqual(result.motion_data.graph_bytes, []);
  assert.equal("marker" in result, false);
  assert.deepEqual(result.sight_obstacles[0]!.material_indices, []);
  assert.equal(result.doors[0]!.sector_out, 0);
  assert.equal(result.doors[0]!.sector_in, 2);
  assert.deepEqual(result.doors[0]!.point_out, [380, 350]);
  delete document.sourceMap;
  document.objects[0]!.source = { map: "other", obstacle: 0 };
  document.objects[0]!.obstacle = undefined;
  assert.deepEqual(compileAssetGameplay(document, assets, bounds), result);
});
test("movement blocker holes preserve walkable islands and invalid contours fail", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.doors = [];
  hut.gameplay!.movementBlockers = [
    {
      id: "courtyard-wall",
      node: "building-999",
      polygon: [
        [10, 10],
        [80, 10],
        [80, 80],
        [10, 80],
      ],
      height: 0,
      holes: [
        [
          [15, 15],
          [70, 15],
          [70, 70],
          [15, 70],
        ],
      ],
    },
  ];
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.equal(compiled.motion_data.layers[0]!.length, 3);
  hut.gameplay!.movementBlockers[0]!.height = [0, 0, 1, 0];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /must be planar/);
});
test("moving, rotating and duplicating assets rebuilds their geometry and connections", () => {
  const { document, assets } = assetCompilerFixture();
  const before = compileAssetGameplay(document, assets, bounds);
  for (const part of document.objects) {
    part.transform.dx += 200;
    part.transform.dy += 100;
  }
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    moved.doors[0]!.point_out,
    before.doors[0]!.point_out.map((v, i) => v + (i ? 100 : 200)),
  );
  // Duplicate the complete asset; local IDs and provenance are intentionally identical.
  const clone = structuredClone(document.objects[0]!);
  clone.id = "hut-b-body";
  clone.group = "hut-b";
  clone.transform = { ...IDENTITY_TRANSFORM };
  document.objects.push(clone);
  document.groups.push({
    id: "hut-b",
    transform: { ...IDENTITY_TRANSFORM, dx: 1100, dy: 400, rot_deg: 90 },
  });
  const duplicated = compileAssetGameplay(document, assets, bounds);
  assert.equal(duplicated.doors.length, 2);
  assert.equal(duplicated.sight_obstacles.length, 2);
  const door = duplicated.doors[1]!;
  assert.notEqual(door.sector_in, duplicated.doors[0]!.sector_in);
  assert.equal(door.point_in[0], door.point_out[0]);
  assert.equal(door.point_in[1] - door.point_out[1], 23); // 40 * sin(35°), quantized
});
test("missing metadata and disconnected doors fail; no level-data fallback", () => {
  const { document, assets, hut } = assetCompilerFixture();
  delete hut.gameplay;
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /Missing asset gameplay definitions.*hut/,
  );
  const fresh = assetCompilerFixture();
  fresh.hut.gameplay!.doors[0]!.inside = [500, 500, 0];
  assert.throws(
    () => compileAssetGameplay(fresh.document, fresh.assets, bounds),
    /inside must resolve/,
  );
  fresh.hut.gameplay!.doors[0]!.node = "absent";
  assert.throws(
    () => validateAssetGameplay(fresh.hut.gameplay, fresh.hut),
    /unknown gameplay node/,
  );
});
test("passages without click polygons retain their navigation endpoints", () => {
  const { document, assets, hut } = assetCompilerFixture();
  const before = compileAssetGameplay(document, assets, bounds);
  hut.gameplay!.doors[0]!.polygon = [];
  const result = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    result.doors,
    before.doors.map((d) => ({ ...d, door_sector: { points: [] } })),
  );
  hut.gameplay!.doors[0]!.polygon = [
    [1, 1],
    [2, 2],
  ];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /invalid gameplay polygon/);
});

test("connection errors distinguish blocked geometry from a height mismatch", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.doors[0]!.outside = [45, 45, 0];
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /projected \[345,345\].*"blocked":true/,
  );
  hut.gameplay!.doors[0]!.outside = [20, 20, 1];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /"height":0,"blocked":false/);
});
test("door transition lock rules remain asset-local and survive placement", () => {
  const { document, assets, hut } = assetCompilerFixture();
  const door = hut.gameplay!.doors[0]!;
  door.locked = true;
  door.unlockable = true;
  door.type = 7;
  door.afterTransition = {
    locked: false,
    unlockable: false,
    lockedVillains: true,
    lockedCivilians: true,
  };
  const result = compileAssetGameplay(document, assets, bounds).doors[0]!;
  assert.equal(result.door_type, 7);
  assert.equal(result.locked_pc, true);
  assert.equal(result.locked_pc_after_patch, false);
  assert.equal(result.unlockable_after_patch, false);
  assert.equal(result.locked_npc_villain_after_patch, true);
  assert.equal(result.locked_npc_civilian_after_patch, true);
  for (const part of document.objects) part.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds).doors[0]!;
  assert.deepEqual(moved.point_in, [result.point_in[0] + 100, result.point_in[1]]);
  assert.equal(moved.locked_npc_villain_after_patch, true);
});
test("adjacent same-height asset surfaces are joined without a blocking seam", () => {
  const { document, assets, hut } = assetCompilerFixture();
  hut.gameplay!.surfaces[1]!.polygon = [
    [90, 0],
    [200, 0],
    [200, 100],
    [90, 100],
  ];
  hut.gameplay!.doors = [];
  const result = compileAssetGameplay(document, assets, bounds);
  assert.equal(result.motion_data.layers[0]!.length, 1);
  assert.equal(result.motion_data.layers[0]![0]!.obstacles.length, 1);
});

test("elevation translates motion in projected coordinates while sight remains in world coordinates", () => {
  const { document, assets } = assetCompilerFixture();
  for (const part of document.objects) part.transform.dz = 100;
  const result = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(result.doors[0]!.point_out, [380, 250]);
  assert.equal(result.sight_obstacles[0]!.points[0]!.y, 340);
  assert.equal(result.sight_obstacles[0]!.points[0]!.z_bottom, 100);
  assert.deepEqual(result.motion_data.layers[0]![0]!.polygon.points[0], [300, 200]);
  const floor = result.sight_obstacles.find(
    (o) => Array.isArray(o.projection_area) && o.projection_area[0] === 0,
  )!;
  assert.equal(floor.points[0]!.z_top, 100);
  assert.equal(floor.points[0]!.y, 300);
});

test("sloped surfaces preserve height, holes and the intersecting slice of solids", () => {
  const { document, assets, hut } = slopedAssetCompilerFixture();
  const result = compileAssetGameplay(document, assets, bounds);
  const area = result.motion_data.layers[0]![0]!;
  assert.equal(area.obstacles.length, 2); // Authored hole and the solid crossing the ramp.
  const projection = result.sight_obstacles.find((o) => Array.isArray(o.projection_area))!;
  assert.deepEqual(
    projection.points.map((p) => p.z_top),
    [0, 100, 100, 0],
  );
  // Raise the solid above the whole ramp; it must stop blocking navigation.
  for (const point of hut.parts[0]!.obstacle_local_game!.points) {
    point.z_bottom = 110;
    point.z_top = 140;
  }
  assert.equal(
    compileAssetGameplay(document, assets, bounds).motion_data.layers[0]![0]!.obstacles.length,
    1,
  );
});

test("sloped asset placement transforms the height plane without mission content", () => {
  const { document, assets } = slopedAssetCompilerFixture();
  document.objects[1]!.group = "hut-a";
  document.groups[0]!.transform = { ...IDENTITY_TRANSFORM, dx: 800, dy: 200, rot_deg: 90, dz: 30 };
  const result = compileAssetGameplay(document, assets, bounds);
  const surface = result.sight_obstacles.find((o) => Array.isArray(o.projection_area))!;
  const plane = heightPlane(surface.points.map((p) => [p.x, p.y - p.z_top, p.z_top]));
  for (const p of surface.points)
    assert.ok(Math.abs(planeHeight(plane, [p.x, p.y - p.z_top]) - p.z_top) < 1e-4);
  assert.ok(Math.max(...surface.points.map((p) => p.z_top)) > 129);
});

test("non-planar and degenerate surfaces fail instead of silently flattening", () => {
  const { document, assets, hut } = slopedAssetCompilerFixture();
  hut.gameplay!.surfaces[0]!.height = [0, 100, 110, 0];
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /must be planar/);
  hut.gameplay!.surfaces[0]!.polygon = [
    [0, 0],
    [10, 0],
    [20, 0],
  ];
  hut.gameplay!.surfaces[0]!.height = 0;
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /nondegenerate/);
});

test("ordinary passages can connect to a lift surface in either direction", () => {
  const { hut, document, assets } = liftAssetCompilerFixture();
  const low = hut.gameplay!.lifts![0]!.doors[0]!;
  for (const reverse of [false, true]) {
    hut.gameplay!.doors = [
      {
        ...low,
        id: "passage",
        type: 0,
        outside: reverse ? low.inside : low.outside,
        inside: reverse ? low.outside : low.inside,
      },
    ];
    const compiled = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
    const door = compiled.doors[0]!;
    assert.equal(reverse ? door.sector_out : door.sector_in, compiled.lifts![0]!.motion_area_index);
    assert.equal(reverse ? door.layer_out : door.layer_in, compiled.motion_data.layers.length - 1);
    assert.equal(door.door_type, 0);
  }
});

test("lift surfaces use the reserved layer and rebuild endpoint references", () => {
  const { document, assets } = liftAssetCompilerFixture();
  const result = compileAssetGameplay(document, assets, bounds);
  assert.equal(result.motion_data.layers.length, 3);
  assert.equal(result.motion_data.layers.at(-1)![0]!.is_lift, true);
  assert.equal(result.doors.length, 0);
  const lift = result.lifts![0]!;
  assert.equal(lift.lift_type, 1);
  assert.equal(lift.direction, 4);
  assert.equal(lift.motion_area_index, 3); // Ground blocker occupies sector 1.
  assert.deepEqual(
    lift.doors.map((d) => d.layer_out),
    [0, 1],
  );
  assert.ok(lift.doors.every((d) => d.layer_in === 2 && d.sector_in === 3));
  const clone = structuredClone(document.objects[0]!);
  clone.id = "stairs-copy";
  clone.group = "stairs-copy";
  clone.transform = { ...IDENTITY_TRANSFORM };
  document.objects.push(clone);
  document.groups.push({
    id: "stairs-copy",
    transform: { ...IDENTITY_TRANSFORM, dx: 1000, dy: 700, rot_deg: 90 },
  });
  const duplicated = compileAssetGameplay(document, assets, bounds);
  assert.equal(duplicated.lifts!.length, 2);
  assert.notEqual(duplicated.lifts![0]!.motion_area_index, duplicated.lifts![1]!.motion_area_index);
  assert.equal(duplicated.lifts![1]!.direction, 8);
});

test("lift validation rejects missing traversal endpoints and mismatched surface ownership", () => {
  const { hut, document, assets } = liftAssetCompilerFixture();
  hut.gameplay!.lifts![0]!.doors.pop();
  assert.throws(
    () => compileAssetGameplay(document, assets, bounds),
    /at least two traversal doors/,
  );
  hut.gameplay!.lifts![0]!.surface = "absent";
  assert.throws(() => compileAssetGameplay(document, assets, bounds), /needs its own surface/);
});

test("interior entrances share a fresh virtual sector independent of motion polygons", () => {
  const { document, assets } = interiorAssetCompilerFixture();
  const result = compileAssetGameplay(document, assets, bounds);
  const doors = result.buildings![0]!.Building.doors;
  assert.equal(result.doors.length, 1);
  assert.equal(doors.length, 2);
  assert.ok(doors.every((d) => d.sector_in === 4 && d.layer_in === 1 && d.sector_out === 0));
  assert.equal(doors[1]!.locked_pc, true);
  assert.ok(doors.every((d) => d.locked_npc_civilian));
  const clone = structuredClone(document.objects[0]!);
  clone.id = "house-copy";
  clone.group = "house-copy";
  clone.transform.dx += 600;
  document.objects.push(clone);
  document.groups.push({ id: "house-copy", transform: { ...IDENTITY_TRANSFORM } });
  const duplicated = compileAssetGameplay(document, assets, bounds);
  assert.equal(duplicated.buildings!.length, 2);
  assert.notEqual(
    duplicated.buildings![0]!.Building.doors[0]!.sector_in,
    duplicated.buildings![1]!.Building.doors[0]!.sector_in,
  );
});
