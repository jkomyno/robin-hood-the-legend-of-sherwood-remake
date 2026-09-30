import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import type { TerrainGrid, MapCamera } from "@rle/shared";
import {
  moveTerrainVertex,
  moveTerrainVertices,
  type TerrainEditMode,
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
  const handles = controls.root.children.find((o) => o instanceof THREE.Points) as THREE.Points;
  assert.equal(handles.geometry.getAttribute("position").count, 4);
  assert.equal(
    terrainVertexFromHit({ object: handles, index: 2 } as THREE.Intersection, grid()),
    "c",
  );

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

test("multi-vertex edits validate the final mesh atomically and preserve offsets", () => {
  const original = grid();
  original.vertices[1]!.position[2] = 15;
  assert.equal(moveTerrainVertices(original, ["a"], [100, 0, 0]), null);
  const moved = moveTerrainVertices(original, ["a", "b", "c", "d"], [100, 20, 30])!;
  assert.ok(moved);
  for (let i = 0; i < 4; i++) {
    assert.deepEqual(
      moved.vertices[i]!.position,
      original.vertices[i]!.position.map((value, axis) => value + [100, 20, 30][axis]!),
    );
  }
  assert.deepEqual(original.vertices[0]!.position, [0, 0, 0]);
  assert.equal(moveTerrainVertices(original, ["a", "b"], [0, 150, 0]), null);
  assert.equal(moveTerrainVertices(original, ["a", "b"], [0, 0, NaN]), null);
});

function interactionHarness(initial: string[] = []) {
  const oldWindow = globalThis.window;
  const windowEvents = new EventTarget();
  Object.assign(globalThis, { window: windowEvents });
  const canvas = new EventTarget() as unknown as HTMLCanvasElement;
  Object.assign(canvas, {
    style: {},
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 500, height: 500 }),
  });
  const captures = new Set<number>();
  canvas.setPointerCapture = (id) => {
    captures.add(id);
  };
  canvas.hasPointerCapture = (id) => captures.has(id);
  canvas.releasePointerCapture = (id) => {
    captures.delete(id);
  };
  const commits: TerrainGrid[] = [],
    previews: (TerrainGrid | null)[] = [];
  const controls = new TerrainControls((value) => previews.push(value));
  const abort = new AbortController();
  let selected = initial,
    selectedCells: string[] = [],
    restored = 0;
  const mode: TerrainEditMode = {
    grid: grid(),
    camera,
    selectedVertices: initial,
    selectVertices(ids) {
      selected = ids;
      mode.selectedVertices = ids;
      controls.setMode({ ...mode });
    },
    selectCells(ids) {
      selectedCells = ids;
      mode.selectedCells = ids;
    },
    commit(value) {
      commits.push(value);
    },
  };
  controls.setMode(mode);
  controls.setup(
    canvas,
    (x, y) => new THREE.Raycaster(new THREE.Vector3(x, -y, 1000), new THREE.Vector3(0, 0, -1)),
    () => () => {
      restored++;
    },
    abort.signal,
    (point) => ({ x: point.x, y: -point.y }),
  );
  function pointer(
    type: string,
    x: number,
    y: number,
    options: { button?: number; shiftKey?: boolean; altKey?: boolean } = {},
  ) {
    const event = new Event(type, { cancelable: true });
    Object.assign(event, {
      clientX: x,
      clientY: y,
      pointerId: 1,
      button: 0,
      shiftKey: false,
      altKey: false,
      ...options,
    });
    canvas.dispatchEvent(event);
    return event;
  }
  function escape() {
    const event = new Event("keydown", { cancelable: true });
    Object.assign(event, { key: "Escape" });
    windowEvents.dispatchEvent(event);
  }
  return {
    controls,
    mode,
    commits,
    previews,
    pointer,
    escape,
    selected: () => selected,
    selectedCells: () => selectedCells,
    restored: () => restored,
    dispose() {
      abort.abort();
      controls.dispose();
      Object.assign(globalThis, { window: oldWindow });
    },
  };
}

test("Shift click toggles vertices without committing or moving them", () => {
  const h = interactionHarness(["a"]);
  try {
    h.pointer("pointerdown", 100, 0, { shiftKey: true });
    h.pointer("pointerup", 100, 0, { shiftKey: true });
    assert.deepEqual(new Set(h.selected()), new Set(["a", "b"]));
    h.pointer("pointerdown", 0, 0, { shiftKey: true });
    h.pointer("pointerup", 0, 0, { shiftKey: true });
    assert.deepEqual(h.selected(), ["b"]);
    assert.equal(h.commits.length, 0);
    assert.ok(h.previews.every((value) => value === null));
  } finally {
    h.dispose();
  }
});

test("right marquee replaces, Shift adds, and Escape cancels selection", () => {
  const h = interactionHarness(["d"]);
  try {
    h.pointer("pointerdown", -10, -10, { button: 2 });
    h.pointer("pointermove", 110, 10, { button: 2 });
    h.pointer("pointerup", 110, 10, { button: 2 });
    assert.deepEqual(new Set(h.selected()), new Set(["a", "b"]));
    h.pointer("pointerdown", 90, 160, { button: 2, shiftKey: true });
    h.pointer("pointermove", 110, 190, { button: 2, shiftKey: true });
    h.pointer("pointerup", 110, 190, { button: 2, shiftKey: true });
    assert.deepEqual(new Set(h.selected()), new Set(["a", "b", "c"]));
    h.pointer("pointerdown", -10, 160, { button: 2 });
    h.pointer("pointermove", 10, 190, { button: 2 });
    h.escape();
    h.pointer("pointerup", 10, 190, { button: 2 });
    assert.deepEqual(new Set(h.selected()), new Set(["a", "b", "c"]));
    assert.equal(h.commits.length, 0);
  } finally {
    h.dispose();
  }
});

test("edge hover and drag target both endpoints, while a vertex takes priority", () => {
  const h = interactionHarness();
  try {
    h.pointer("pointermove", 50, 0);
    assert.deepEqual(new Set(h.controls.root.userData.terrainHoverVertices), new Set(["a", "b"]));
    h.pointer("pointermove", 0, 0);
    assert.deepEqual(h.controls.root.userData.terrainHoverVertices, ["a"]);
    h.pointer("pointerdown", 50, 0);
    h.pointer("pointermove", 50, -20);
    h.pointer("pointerup", 50, -20);
    assert.equal(h.commits.length, 1);
    const moved = h.commits[0]!;
    assert.ok(moved.vertices[0]!.position[2] > 0);
    assert.equal(moved.vertices[0]!.position[2], moved.vertices[1]!.position[2]);
    assert.equal(moved.vertices[2]!.position[2], 0);
    assert.equal(moved.vertices[3]!.position[2], 0);
  } finally {
    h.dispose();
  }
});

test("cell drag moves its full vertex set and Alt controls horizontal movement", () => {
  const h = interactionHarness();
  try {
    h.pointer("pointermove", 50, 80);
    assert.deepEqual(
      new Set(h.controls.root.userData.terrainHoverVertices),
      new Set(["a", "b", "c", "d"]),
    );
    h.pointer("pointerdown", 50, 80, { altKey: true });
    h.pointer("pointermove", 65, 90, { altKey: true });
    h.pointer("pointerup", 65, 90, { altKey: true });
    assert.equal(h.commits.length, 1);
    for (let i = 0; i < 4; i++) {
      const a = h.mode.grid.vertices[i]!.position,
        b = h.commits[0]!.vertices[i]!.position;
      assert.ok(Math.abs(b[0] - a[0] - 15) < 1e-8);
      assert.ok(Math.abs(b[1] - a[1] - 10 * Math.sin((35 * Math.PI) / 180)) < 1e-8);
      assert.equal(b[2], a[2]);
    }
  } finally {
    h.dispose();
  }
});

test("dragging a selected target moves the full selection and Escape restores preview", () => {
  const h = interactionHarness(["a", "b"]);
  try {
    h.pointer("pointermove", 0, 0);
    assert.deepEqual(new Set(h.controls.root.userData.terrainHoverVertices), new Set(["a", "b"]));
    h.pointer("pointerdown", 0, 0);
    h.pointer("pointermove", 0, -20);
    const preview = h.previews.at(-1)!;
    assert.equal(preview.vertices[0]!.position[2], preview.vertices[1]!.position[2]);
    assert.ok(preview.vertices[0]!.position[2] > 0);
    h.escape();
    h.pointer("pointerup", 0, -20);
    assert.equal(h.commits.length, 0);
    assert.equal(h.previews.at(-1), null);
    assert.equal(h.restored(), 1);
  } finally {
    h.dispose();
  }
});

test("Shift edge and cell toggles use the complete target vertex set", () => {
  const h = interactionHarness(["a"]);
  try {
    h.pointer("pointerdown", 50, 0, { shiftKey: true });
    h.pointer("pointerup", 50, 0, { shiftKey: true });
    assert.deepEqual(new Set(h.selected()), new Set(["a", "b"]));
    h.pointer("pointerdown", 50, 0, { shiftKey: true });
    h.pointer("pointerup", 50, 0, { shiftKey: true });
    assert.deepEqual(h.selected(), []);
    h.pointer("pointerdown", 50, 80, { shiftKey: true });
    h.pointer("pointerup", 50, 80, { shiftKey: true });
    assert.deepEqual(new Set(h.selected()), new Set(["a", "b", "c", "d"]));
    h.pointer("pointerdown", 50, 80, { shiftKey: true });
    h.pointer("pointerup", 50, 80, { shiftKey: true });
    assert.deepEqual(h.selected(), []);
    assert.equal(h.commits.length, 0);
  } finally {
    h.dispose();
  }
});

test("marquee selects complete cells only when every corner is enclosed", () => {
  const h = interactionHarness();
  try {
    h.pointer("pointerdown", -10, -10, { button: 2 });
    h.pointer("pointermove", 110, 190, { button: 2 });
    h.pointer("pointerup", 110, 190, { button: 2 });
    assert.deepEqual(new Set(h.selected()), new Set(["a", "b", "c", "d"]));
    assert.deepEqual(h.selectedCells(), ["cell"]);
    h.pointer("pointerdown", -10, -10, { button: 2 });
    h.pointer("pointermove", 110, 10, { button: 2 });
    h.pointer("pointerup", 110, 10, { button: 2 });
    assert.deepEqual(h.selectedCells(), []);
  } finally {
    h.dispose();
  }
});

test("empty left drags remain available to camera pan while right drags select", () => {
  const h = interactionHarness(["a"]);
  try {
    assert.equal(h.pointer("pointerdown", -100, -100).defaultPrevented, false);
    assert.deepEqual(h.selected(), []);
    assert.equal(h.pointer("pointermove", -120, -120).defaultPrevented, false);
    assert.equal(h.pointer("pointerup", -120, -120).defaultPrevented, false);
    assert.equal(h.restored(), 0);
    assert.equal(h.pointer("pointerdown", -100, -100, { button: 2 }).defaultPrevented, true);
    assert.equal(h.pointer("pointermove", -120, -120, { button: 2 }).defaultPrevented, true);
    assert.equal(h.pointer("pointerup", -120, -120, { button: 2 }).defaultPrevented, true);
    assert.equal(h.restored(), 1);
    assert.equal(h.commits.length, 0);
  } finally {
    h.dispose();
  }
});
