import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import type { TerrainGrid, MapCamera } from "@rle/shared";
import {
  moveTerrainVertex,
  terrainHorizontalPoint,
  TerrainControls,
  terrainVertexFromHit,
} from "./terrain-controls.ts";
const camera: MapCamera = { kind: "oblique-orthographic", elevation_deg: 35 };
function grid(): TerrainGrid {
  return {
    version: 1,
    spacing: 100,
    vertices: [
      { id: "a", position: [0, 0, 0] },
      { id: "b", position: [100, 0, 0] },
      { id: "c", position: [100, 100, 0] },
      { id: "d", position: [0, 100, 0] },
    ],
    cells: [{ id: "cell", vertices: [0, 1, 2, 3], material: "grass_short" }],
  };
}
test("grid edit preserves other vertices and input while accepting XYZ changes", () => {
  const original = grid();
  const next = moveTerrainVertex(original, "a", [10, 10, 40])!;
  assert.deepEqual(next.vertices[0]!.position, [10, 10, 40]);
  assert.deepEqual(original.vertices[0]!.position, [0, 0, 0]);
  assert.equal(next.vertices[1], original.vertices[1]);
  assert.equal(next.cells, original.cells);
});
test("grid edit rejects collapsed, inverted, and nonfinite candidates", () => {
  const original = grid();
  assert.equal(moveTerrainVertex(original, "a", [100, 0, 0]), null);
  assert.equal(moveTerrainVertex(original, "a", [200, 200, 0]), null);
  assert.equal(moveTerrainVertex(original, "a", [0, 0, NaN]), null);
  assert.throws(() => moveTerrainVertex(original, "missing", [0, 0, 0]), /Unknown terrain vertex/);
});
test("horizontal drag samples the starting elevation using map-pixel coordinates", () => {
  const ray = new THREE.Ray(new THREE.Vector3(20, -40, 300), new THREE.Vector3(0, 0, -1));
  const point = terrainHorizontalPoint(ray, camera, 30)!;
  assert.equal(point[0], 20);
  assert.ok(Math.abs(point[1] - 40 * Math.sin((35 * Math.PI) / 180)) < 1e-8);
  assert.equal(point[2], 30);
  assert.equal(
    terrainHorizontalPoint(
      new THREE.Ray(new THREE.Vector3(), new THREE.Vector3(1, 0, 0)),
      camera,
      30,
    ),
    null,
  );
});
test("controls batch vertex handles and draw all cell perimeter edges", () => {
  const controls = new TerrainControls(() => {});
  controls.setMode({ grid: grid(), camera, selectedVertex: "a", commit() {} });
  assert.equal(
    controls.root.children.filter((o) => typeof o.userData.terrainVertex === "string").length,
    1,
  );
  const handles = controls.root.children.find((o) => o instanceof THREE.Points) as THREE.Points;
  assert.equal(handles.geometry.getAttribute("position").count, 4);
  assert.equal(
    terrainVertexFromHit({ object: handles, index: 2 } as THREE.Intersection, grid()),
    "c",
  );
  assert.equal(controls.root.children.length, 3);
  const lines = controls.root.children.find(
    (o) => o instanceof THREE.LineSegments,
  ) as THREE.LineSegments;
  assert.equal(lines.geometry.getAttribute("position").count, 8);
  controls.dispose();
  assert.equal(controls.root.children.length, 0);
});

test("vertex gesture previews until release, commits once, and Escape cancels", () => {
  const oldWindow = globalThis.window;
  const windowEvents = new EventTarget();
  Object.assign(globalThis, { window: windowEvents });
  const canvas = new EventTarget() as EventTarget & {
    setPointerCapture(id: number): void;
    hasPointerCapture(id: number): boolean;
    releasePointerCapture(id: number): void;
  };
  const captures = new Set<number>();
  canvas.setPointerCapture = (id) => {
    captures.add(id);
  };
  canvas.hasPointerCapture = (id) => captures.has(id);
  canvas.releasePointerCapture = (id) => {
    captures.delete(id);
  };
  const commits: TerrainGrid[] = [];
  const previews: (TerrainGrid | null)[] = [];
  let restored = 0;
  const controls = new TerrainControls((value) => previews.push(value));
  const signal = new AbortController();
  const mode = {
    grid: grid(),
    camera,
    commit(value: TerrainGrid) {
      commits.push(value);
    },
  };
  const pointer = (type: string, y: number) => {
    const event = new Event(type, { cancelable: true });
    Object.assign(event, { clientX: 0, clientY: y, button: 0, pointerId: 1, shiftKey: false });
    canvas.dispatchEvent(event);
  };
  try {
    controls.setMode(mode);
    controls.setup(
      canvas as unknown as HTMLCanvasElement,
      (x, y) => new THREE.Raycaster(new THREE.Vector3(x, -y, 1000), new THREE.Vector3(0, 0, -1)),
      () => () => {
        restored++;
      },
      signal.signal,
    );
    pointer("pointerdown", 0);
    pointer("pointermove", -20);
    assert.equal(commits.length, 0);
    assert.ok(previews.at(-1)!.vertices[0]!.position[2] > 0);
    pointer("pointerup", -20);
    pointer("pointerup", -20);
    assert.equal(commits.length, 1);
    assert.equal(previews.at(-1), null);
    assert.equal(restored, 1);
    pointer("pointerdown", 0);
    pointer("pointermove", -30);
    const escape = new Event("keydown", { cancelable: true });
    Object.assign(escape, { key: "Escape" });
    windowEvents.dispatchEvent(escape);
    pointer("pointerup", -30);
    assert.equal(commits.length, 1);
    assert.equal(restored, 2);
    assert.equal(previews.at(-1), null);
  } finally {
    signal.abort();
    controls.dispose();
    Object.assign(globalThis, { window: oldWindow });
  }
});
