import test from "node:test";
import assert from "node:assert/strict";
import { createTerrainGrid, terrainHeightAt, type Level3D, type LevelSpline } from "@rle/shared";
import { MapSession } from "./session.ts";
import { followTerrainEdit, followTerrainTransform, terrainAnchor } from "./terrain-follow.ts";

function fixture(): Level3D {
  const terrain = createTerrainGrid([0, 0, 400, 400], 100, 0);
  terrain.vertices.forEach((vertex) => {
    vertex.position[2] = vertex.position[0] / 2;
  });
  return {
    version: 1,
    map: "Test",
    sceneAssets: [],
    size: [400, 400],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    groups: [{ id: "house", transform: { dx: 100, dy: 100, dz: 75, rot_deg: 90 } }],
    objects: [
      {
        id: "roof",
        node: "roof",
        kind: "scenery",
        source: { map: "Test" },
        group: "house",
        transform: { dx: 0, dy: 0, dz: 40, rot_deg: 0 },
      },
      {
        id: "tree",
        node: "tree",
        kind: "scenery",
        source: { map: "Test" },
        transform: { dx: 200, dy: 200, dz: 115, rot_deg: 0 },
      },
    ],
    terrain,
  };
}

test("horizontal asset moves retain offsets, while manual height edits remain literal", () => {
  const document = fixture();
  const selected = { kind: "group" as const, id: "house" };
  const transform = document.groups[0]!.transform;
  assert.equal(followTerrainTransform(document, selected, { ...transform, dx: 200 }).dz, 125);
  assert.equal(followTerrainTransform(document, selected, { ...transform, dz: 250 }).dz, 250);
  assert.equal(
    followTerrainTransform(document, selected, { ...transform, dx: 200, dz: 250 }).dz,
    300,
  );
});

test("terrain reshaping moves groups once and preserves elevated parts and loose objects", () => {
  const before = fixture();
  const terrain = {
    ...before.terrain!,
    vertices: before.terrain!.vertices.map((vertex) => ({
      ...vertex,
      position: [vertex.position[0], vertex.position[1], vertex.position[2] + 30] as [
        number,
        number,
        number,
      ],
    })),
  };
  const after = followTerrainEdit(before, { ...before, terrain });
  assert.equal(after.groups[0]!.transform.dz, 105);
  assert.equal(after.objects[0]!.transform.dz, 40);
  assert.equal(after.objects[1]!.transform.dz, 145);
  assert.equal(before.groups[0]!.transform.dz, 75);
});

test("part movement samples its rotated parent coordinates and undefined terrain keeps height", () => {
  const document = fixture();
  const selected = { kind: "part" as const, id: "roof" };
  assert.ok(terrainAnchor(document, selected).every((value) => Math.abs(value - 100) < 1e-8));
  const transform = document.objects[0]!.transform;
  // Local X on a 90-degree parent maps to ground Y, where this slope is flat.
  assert.ok(
    Math.abs(followTerrainTransform(document, selected, { ...transform, dx: 50 }).dz - 40) < 1e-8,
  );
  assert.equal(
    followTerrainTransform(
      document,
      { kind: "group", id: "house" },
      { ...document.groups[0]!.transform, dx: 500 },
    ).dz,
    75,
  );
});

test("moving and deleting channels preserves asset offsets in the same undo revision", () => {
  const base = fixture();
  base.terrain = createTerrainGrid([0, 0, 400, 400], 100, 0);
  base.groups[0]!.transform.dz = 25;
  base.objects[1]!.transform.dz = 15;
  const river: LevelSpline = {
    id: "river",
    name: "River",
    kind: "river",
    points: [
      [20, 100, 0],
      [380, 100, 0],
    ],
    width: 50,
    closed: false,
    repeatLength: 32,
    channel: { enabled: true, bedDepth: 20, bankSlope: 1 },
  };
  const session = new MapSession<Level3D, null>();
  session.publish(session.beginLoad(), "Test", base, null);
  const add = followTerrainEdit(base, { ...base, splines: [river] });
  session.edit(add);
  assert.ok(Math.abs(add.groups[0]!.transform.dz - 5) < 1e-6);
  assert.equal(add.objects[0]!.transform.dz, 40, "group children retain their relative height");
  const moved: LevelSpline = {
    ...river,
    points: [
      [20, 200, 0],
      [380, 200, 0],
    ],
  };
  const move = followTerrainEdit(add, { ...add, splines: [moved] });
  session.edit(move);
  assert.ok(Math.abs(move.groups[0]!.transform.dz - 25) < 1e-6);
  assert.ok(Math.abs(move.objects[1]!.transform.dz + 5) < 1e-6);
  assert.ok(Math.abs(move.objects[1]!.transform.dz - terrainHeightAt(move, 200, 200)! - 15) < 1e-6);
  const remove = followTerrainEdit(move, { ...move, splines: [] });
  session.edit(remove);
  assert.ok(Math.abs(remove.objects[1]!.transform.dz - 15) < 1e-6);
  session.undo();
  assert.strictEqual(session.current!.document, move);
  session.undo();
  assert.strictEqual(session.current!.document, add);
  session.redo();
  assert.strictEqual(session.current!.document, move);
  assert.strictEqual(
    base.terrain,
    move.terrain,
    "derived channels never replace the authored grid",
  );
});
