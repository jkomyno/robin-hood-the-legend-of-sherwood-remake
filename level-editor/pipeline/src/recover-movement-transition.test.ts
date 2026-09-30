import test from "node:test";
import assert from "node:assert/strict";
import type { SightObstacle, Point } from "@rle/shared";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { sightTransitionCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { recoverMovementTransition } from "./recover-movement-transition.ts";

test("recovered movement and sight states recompile independently of source indices", () => {
  const { document, assets, hut } = sightTransitionCompilerFixture();
  const original = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const obstacles = original.motion_data.layers.flatMap((layer) =>
    layer.flatMap((area) => area.obstacles),
  );
  hut.gameplay!.movementTransitions = [
    recoverMovementTransition({
      id: "barriers",
      node: "building-999",
      patch: {
        active: true,
        definitive: false,
        waypoint: [320, 320],
        apply_sector: { points: [] },
        no_apply_sector: { points: [] },
      },
      initial: obstacles.filter((obstacle) => obstacle.state_id === 1),
      applied: obstacles.filter((obstacle) => obstacle.state_id === 2),
      initialSight: ["building-999"],
      appliedSight: ["open-barrier"],
      receivers: [],
      groundLayer: true,
      waypointHeight: 0,
      localize: ([x, y, z]) => [x - 300, y - 300, z],
    }),
  ];
  const recovered = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  assert.deepEqual(recovered.motion_data, original.motion_data);
  assert.deepEqual(recovered.movement_transitions, original.movement_transitions);
  for (const part of document.objects) part.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  assert.deepEqual(moved.movement_transitions![0]!.waypoint, [420, 320]);
  assert.equal(moved.motion_data.layers[0]![0]!.obstacles[0]!.polygon.points[0]![0], 445);
});

test("changing contours split across receiving planes and retain ground holes", () => {
  const shape: Point[] = [
    [0, 0],
    [30, 0],
    [30, 10],
    [0, 10],
  ];
  const receiver: SightObstacle = {
    points: [
      [10, 2],
      [20, 2],
      [20, 8],
      [10, 8],
    ].map(([x, y]) => ({ x: x!, y: y! + 20, z_bottom: 0, z_top: 20 })),
    projection_area: [0, 0],
    solid: true,
    opaque: true,
    mouse: true,
    show_shadow_polygon: true,
    default_material: 0,
    material_indices: [],
  };
  receiver.points[3]!.z_top += 0.01;
  receiver.points[3]!.y += 0.01;
  const options: Parameters<typeof recoverMovementTransition>[0] = {
    id: "barrier",
    node: "frame",
    patch: {
      active: false,
      definitive: true,
      waypoint: [5, 5],
      apply_sector: { points: shape },
      no_apply_sector: { points: [] },
    },
    initial: [{ state_id: 1, polygon: { points: shape } }],
    applied: [],
    initialSight: [],
    appliedSight: ["raised"],
    receivers: [receiver],
    groundLayer: true,
    waypointHeight: 0,
    localize: ([x, y, z]) => [x - 100, y - 200, z - 5],
  };
  const transition = recoverMovementTransition(options);
  assert.equal(transition.initial.length, 2);
  assert.deepEqual(
    transition.initial.map((surface) => [...new Set(surface.height as number[])]),
    [[15], [-5]],
  );
  assert.equal(transition.initial[1]!.holes!.length, 1);
  assert.deepEqual(transition.waypoint, [-95, -195, -5]);
  assert.deepEqual(
    transition.applyPolygon,
    shape.map(([x, y]) => [x - 100, y - 200]),
  );
  assert.throws(
    () => recoverMovementTransition({ ...options, groundLayer: false }),
    /uncovered elevated/,
  );
  const before = structuredClone(receiver);
  const authored = recoverMovementTransition({
    ...options,
    groundLayer: false,
    uncoveredPlane: [0, 0, 20],
  });
  assert.equal(authored.initial.length, 2);
  assert.ok(
    authored.initial.every(
      (surface) => Array.isArray(surface.height) && surface.height.every((z) => z === 15),
    ),
  );
  assert.equal(authored.initial[1]!.holes!.length, 1);
  assert.deepEqual(receiver, before);
  assert.throws(
    () => recoverMovementTransition({ ...options, uncoveredPlane: [0, 0, NaN] }),
    /must be finite/,
  );
});
