import test from "node:test";
import assert from "node:assert/strict";
import { routePose, routeSchedule } from "./population-motion.ts";
import {
  validatePopulation,
  type MapCamera,
  type Population,
  type PopulationRoute,
} from "@rle/shared";
const camera: MapCamera = { kind: "oblique-orthographic", elevation_deg: 35 };
const route: PopulationRoute = {
  id: "watch",
  name: "Gate watch",
  mode: "ping-pong",
  speed: 10,
  points: [
    { position: [0, 0, 0], wait: 2, direction: 0 },
    { position: [100, 0, 0], wait: 3, direction: 8 },
  ],
};
test("patrol waits, travels, faces its station and reverses at its endpoint", () => {
  const schedule = routeSchedule(route, camera);
  assert.equal(schedule.duration, 25);
  assert.deepEqual(routePose(schedule, 1), { position: [0, 0, 0], direction: 0, walking: false });
  assert.deepEqual(routePose(schedule, 7), { position: [50, 0, 0], direction: 4, walking: true });
  assert.deepEqual(routePose(schedule, 13), {
    position: [100, 0, 0],
    direction: 8,
    walking: false,
  });
  assert.deepEqual(routePose(schedule, 20), { position: [50, 0, 0], direction: 12, walking: true });
  assert.deepEqual(routePose(schedule, 26), routePose(schedule, 1));
});
test("loop closes while a three-stop patrol retraces the intermediate station", () => {
  const points = [
    ...route.points,
    { position: [100, 100, 0] as [number, number, number], wait: 0 },
  ];
  assert.deepEqual(
    routeSchedule({ ...route, points }, camera).legs.map((l) => l.from.position),
    [points[0].position, points[1].position, points[2].position, points[1].position],
  );
  const loop = routeSchedule({ ...route, points, mode: "loop" }, camera);
  assert.equal(loop.legs.length, 3);
  assert.deepEqual(loop.legs[2].to.position, points[0].position);
});
test("route speed accounts for the ground projection and elevation", () => {
  const slope = {
    ...route,
    points: [
      { position: [0, 0, 0] as [number, number, number], wait: 0 },
      {
        position: [
          0,
          Math.sin((35 * Math.PI) / 180) * 100,
          Math.cos((35 * Math.PI) / 180) * 100,
        ] as [number, number, number],
        wait: 0,
      },
    ],
  };
  assert.ok(Math.abs(routeSchedule(slope, camera).duration - 20 * Math.SQRT2) < 1e-8);
});
function population(): Population {
  return {
    version: 1,
    spriteCatalog: "population/town/sprites.json",
    routes: [structuredClone(route)],
    actors: [
      {
        id: "guard",
        name: "Sentry",
        role: "soldier",
        sprite: "guard",
        position: [0, 0, 0],
        direction: 0,
        duty: "Watch the gate",
        route: "watch",
      },
    ],
    items: [],
  };
}
test("population survives JSON and rejects missing routes, bad positions and duplicate IDs", () => {
  validatePopulation(JSON.parse(JSON.stringify(population())));
  const missing = population();
  missing.actors[0].route = "absent";
  assert.throws(() => validatePopulation(missing), /missing route/);
  const duplicate = population();
  duplicate.actors[0].id = "watch";
  assert.throws(() => validatePopulation(duplicate), /duplicate/);
  const bad = population();
  bad.actors[0].position[0] = NaN;
  assert.throws(() => validatePopulation(bad), /position/);
  const path = population();
  path.spriteCatalog = "../outside.json";
  assert.throws(() => validatePopulation(path), /catalog/);
});
