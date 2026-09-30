import assert from "node:assert/strict";
import test from "node:test";
import { authorMeshGround } from "./author-mesh-ground.ts";
import { gameToScene, type Vec3 } from "../../shared/src/scene.ts";
import { heightPlane, planeHeight } from "../../shared/src/gameplay-plane.ts";

const camera = { kind: "oblique-orthographic" as const, elevation_deg: 35 };
const scene = (points: Vec3[]) =>
  new Float32Array(points.flatMap((p) => gameToScene(camera, ...p)));

test("mesh ground preserves nonflat elevations and marks unknown gameplay semantics", async () => {
  const points: Vec3[] = [
    [0, 0, 0],
    [100, 0, 10],
    [100, 100, 20],
    [0, 100, 5],
  ];
  const result = await authorMeshGround(
    scene(points),
    new Uint32Array([0, 1, 2, 0, 2, 3]),
    camera,
    { material: 9 },
  );
  assert.equal(result.gameplay.surfaces.length, 2);
  assert.equal(result.report.authoredTriangles, result.report.sourceTriangles);
  assert.match(result.gameplay.draft!.issues[0]!, /Water, impassable slopes/);
  for (const [i, surface] of result.gameplay.surfaces.entries()) {
    const vertices = surface.polygon.map(([x, y], n): Vec3 => [
      x,
      y,
      (surface.height as number[])[n]!,
    ]);
    const plane = heightPlane(vertices);
    const expected = points[i === 0 ? 1 : 3]!;
    assert.ok(Math.abs(planeHeight(plane, [expected[0], expected[1]]) - expected[2]) < 1e-5);
  }
});

test("mesh ground rejects vertical geometry and invalid indices instead of inventing surfaces", async () => {
  await assert.rejects(
    authorMeshGround(
      scene([
        [0, 0, 0],
        [0, 0, 20],
        [0, 10, 0],
      ]),
      new Uint32Array([0, 1, 2]),
      camera,
      { material: 9 },
    ),
    /nondegenerate/,
  );
  await assert.rejects(
    authorMeshGround(scene([[0, 0, 0]]), new Uint32Array([0, 1, 2]), camera, { material: 9 }),
    /vertex indices/,
  );
});

test("optional simplification retains an existing mesh vertex for every surface corner", async () => {
  const points: Vec3[] = [];
  const indices: number[] = [];
  for (let y = 0; y <= 10; y++) for (let x = 0; x <= 10; x++) points.push([x * 10, y * 10, x + y]);
  for (let y = 0; y < 10; y++)
    for (let x = 0; x < 10; x++) {
      const a = y * 11 + x;
      indices.push(a, a + 1, a + 12, a, a + 12, a + 11);
    }
  const result = await authorMeshGround(scene(points), new Uint32Array(indices), camera, {
    material: 3,
    simplifyError: 0.01,
    targetTriangles: 10,
  });
  assert.ok(result.report.authoredTriangles < result.report.sourceTriangles);
  for (const surface of result.gameplay.surfaces)
    for (let i = 0; i < surface.polygon.length; i++) {
      const [x, y] = surface.polygon[i]!;
      const height = (surface.height as number[])[i]!;
      assert.ok(points.some((p) => Math.hypot(p[0] - x, p[1] - y, p[2] - height) < 1e-5));
    }
  assert.match(result.gameplay.draft!.issues[1]!, /simplified/);
});
