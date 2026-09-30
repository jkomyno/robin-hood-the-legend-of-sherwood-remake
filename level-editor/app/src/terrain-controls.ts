import * as THREE from "three";
import { gameToScene, validateTerrainGrid, type TerrainGrid, type MapCamera } from "@rle/shared";
import { disposeObjectResources } from "./resources.ts";

type Position = [number, number, number];
export interface TerrainEditMode {
  grid: TerrainGrid;
  camera: MapCamera;
  selectedVertex?: string;
  selectVertex?(id: string): void;
  commit(grid: TerrainGrid): void;
  deselect?(): void;
}

const validatedGrids = new WeakSet<TerrainGrid>();
const incidentCells = new WeakMap<TerrainGrid["cells"], Map<number, TerrainGrid["cells"]>>();

/** Validate the immutable base once, then only cells incident to the changed vertex. */
export function moveTerrainVertex(
  grid: TerrainGrid,
  id: string,
  position: Position,
): TerrainGrid | null {
  const index = grid.vertices.findIndex((vertex) => vertex.id === id);
  if (index < 0) throw new Error(`Unknown terrain vertex: ${id}`);
  try {
    if (!validatedGrids.has(grid)) {
      validateTerrainGrid(grid);
      validatedGrids.add(grid);
    }
    if (!position.every(Number.isFinite)) return null;
    let incidents = incidentCells.get(grid.cells);
    if (!incidents) {
      incidents = new Map();
      for (const cell of grid.cells)
        for (const vertex of cell.vertices) {
          const cells = incidents.get(vertex) ?? [];
          cells.push(cell);
          incidents.set(vertex, cells);
        }
      incidentCells.set(grid.cells, incidents);
    }
    const cells = incidents.get(index) ?? [];
    const indices = [...new Set(cells.flatMap((cell) => cell.vertices))];
    const localIndices = new Map(indices.map((vertex, i) => [vertex, i]));
    validateTerrainGrid({
      ...grid,
      vertices: indices.map((i) =>
        i === index ? { ...grid.vertices[i]!, position } : grid.vertices[i]!,
      ),
      cells: cells.map((cell) => ({
        ...cell,
        vertices: cell.vertices.map((i) => localIndices.get(i)!),
      })),
    });
    const vertices = grid.vertices.slice();
    vertices[index] = { ...vertices[index]!, position };
    const next = { ...grid, vertices };
    validatedGrids.add(next);
    return next;
  } catch {
    return null;
  }
}

export function terrainVertexFromHit(
  hit: THREE.Intersection,
  grid: TerrainGrid,
): string | undefined {
  if (typeof hit.object.userData.terrainVertex === "string")
    return hit.object.userData.terrainVertex;
  if (hit.object.userData.terrainVertices && hit.index !== undefined)
    return grid.vertices[hit.index]?.id;
  return undefined;
}

/** Intersect a horizontal drag plane in the controls' local scene frame. */
export function terrainHorizontalPoint(
  ray: THREE.Ray,
  camera: MapCamera,
  height: number,
): Position | null {
  const z = gameToScene(camera, 0, 0, height)[2];
  if (Math.abs(ray.direction.z) < 1e-8) return null;
  const distance = (z - ray.origin.z) / ray.direction.z;
  if (distance < 0) return null;
  const point = ray.at(distance, new THREE.Vector3());
  return [point.x, -point.y * Math.sin((camera.elevation_deg * Math.PI) / 180), height];
}

/** Transient handles and preview; the document owner commits once on release. */
export class TerrainControls {
  readonly root = new THREE.Group();
  private mode: TerrainEditMode | null = null;
  private drag: {
    mode: TerrainEditMode;
    id: string;
    pointer: number;
    position: Position;
    start: Position | null;
    startY: number;
    unitsPerPixel: number;
    horizontal: boolean;
    grid: TerrainGrid;
    moved: boolean;
  } | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private finishOrbit: (() => void) | null = null;
  private preview: (grid: TerrainGrid | null) => void;
  constructor(preview: (grid: TerrainGrid | null) => void) {
    this.preview = preview;
    this.root.renderOrder = 1100;
  }
  setMode(mode: TerrainEditMode | null) {
    this.cancel();
    this.mode = mode;
    this.draw(mode?.grid ?? null);
  }
  show(grid: TerrainGrid | null) {
    this.draw(grid);
  }
  private draw(grid: TerrainGrid | null) {
    disposeObjectResources([this.root]);
    this.root.clear();
    if (!grid || !this.mode) return;
    const points = grid.vertices.map(
      ({ position }) => new THREE.Vector3(...gameToScene(this.mode!.camera, ...position)),
    );
    const handles = new THREE.Points(
      new THREE.BufferGeometry().setFromPoints(points),
      new THREE.PointsMaterial({
        color: 0xffd36b,
        size: 7,
        sizeAttenuation: false,
        depthTest: false,
        depthWrite: false,
      }),
    );
    handles.userData.terrainVertices = true;
    handles.userData.noSunShadow = true;
    handles.renderOrder = 1101;
    this.root.add(handles);
    const selectedIndex = grid.vertices.findIndex((v) => v.id === this.mode!.selectedVertex);
    if (selectedIndex >= 0) {
      const handle = new THREE.Mesh(
        new THREE.SphereGeometry(Math.max(2, Math.min(10, grid.spacing / 14)), 8, 6),
        new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, depthWrite: false }),
      );
      handle.position.copy(points[selectedIndex]!);
      handle.renderOrder = 1102;
      handle.userData.terrainVertex = grid.vertices[selectedIndex]!.id;
      handle.userData.noSunShadow = true;
      this.root.add(handle);
    }
    const edges = new Set<string>();
    const segments: THREE.Vector3[] = [];
    for (const cell of grid.cells)
      for (let i = 0; i < cell.vertices.length; i++) {
        const a = cell.vertices[i]!,
          b = cell.vertices[(i + 1) % cell.vertices.length]!;
        const key = `${Math.min(a, b)}/${Math.max(a, b)}`;
        if (edges.has(key)) continue;
        edges.add(key);
        segments.push(points[a]!, points[b]!);
      }
    const line = new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(segments),
      new THREE.LineBasicMaterial({ color: 0xffd36b, depthTest: false, depthWrite: false }),
    );
    line.renderOrder = 1100;
    line.userData.noSunShadow = true;
    this.root.add(line);
    this.root.updateWorldMatrix(true, true);
  }
  private localRay(ray: THREE.Raycaster): THREE.Ray {
    this.root.updateWorldMatrix(true, false);
    return ray.ray.clone().applyMatrix4(new THREE.Matrix4().copy(this.root.matrixWorld).invert());
  }
  private release() {
    const pointer = this.drag?.pointer;
    this.drag = null;
    if (pointer !== undefined && this.canvas?.hasPointerCapture(pointer))
      this.canvas.releasePointerCapture(pointer);
    this.finishOrbit?.();
    this.finishOrbit = null;
  }
  cancel() {
    if (!this.drag) return;
    this.release();
    this.preview(null);
    this.draw(this.mode?.grid ?? null);
  }
  setup(
    canvas: HTMLCanvasElement,
    ray: (x: number, y: number) => THREE.Raycaster,
    pauseOrbit: () => () => void,
    signal: AbortSignal,
  ) {
    this.canvas = canvas;
    const consume = (event: Event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    canvas.addEventListener(
      "pointerdown",
      (event) => {
        if (!this.mode || this.drag || event.button !== 0) return;
        const mode = this.mode;
        const pick = ray(event.clientX, event.clientY);
        // Match the fixed pixel handle size at the grid's centre depth.
        const handles = this.root.children.find((object) => object instanceof THREE.Points) as
          | THREE.Points
          | undefined;
        if (!handles) return;
        handles.geometry.computeBoundingSphere();
        const centre = handles.geometry
          .boundingSphere!.center.clone()
          .applyMatrix4(handles.matrixWorld);
        const pickPlane = new THREE.Plane().setFromNormalAndCoplanarPoint(
          pick.ray.direction,
          centre,
        );
        const adjacent = ray(event.clientX, event.clientY + 1);
        const centrePoint = pick.ray.intersectPlane(pickPlane, new THREE.Vector3());
        const adjacentPoint = adjacent.ray.intersectPlane(pickPlane, new THREE.Vector3());
        const threshold = pick.params.Points.threshold;
        if (centrePoint && adjacentPoint)
          pick.params.Points.threshold = centrePoint.distanceTo(adjacentPoint) * 6;
        const hit = pick
          .intersectObject(this.root, true)
          .find((h) => terrainVertexFromHit(h, mode.grid) !== undefined);
        pick.params.Points.threshold = threshold;
        if (!hit) return;
        const id = terrainVertexFromHit(hit, mode.grid)!;
        const position = mode.grid.vertices.find((v) => v.id === id)!.position;
        const local = this.localRay(pick);
        const start = terrainHorizontalPoint(local, mode.camera, position[2]);
        if (event.shiftKey && !start) return;
        // Measure screen scale at the handle depth. This also supports elevation
        // edits from a straight-down view, where a vertical-axis ray drag is singular.
        const point = new THREE.Vector3(...gameToScene(mode.camera, ...position));
        const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(local.direction, point);
        const a = local.intersectPlane(plane, new THREE.Vector3());
        const b = this.localRay(ray(event.clientX, event.clientY + 1)).intersectPlane(
          plane,
          new THREE.Vector3(),
        );
        if (!a || !b) return;
        const unitsPerPixel =
          a.distanceTo(b) * Math.cos((mode.camera.elevation_deg * Math.PI) / 180);
        consume(event);
        // Selection can synchronously rebuild the mode; notify before starting the gesture.
        mode.selectVertex?.(id);
        this.drag = {
          mode,
          id,
          pointer: event.pointerId,
          position,
          start,
          startY: event.clientY,
          unitsPerPixel,
          horizontal: event.shiftKey,
          grid: mode.grid,
          moved: false,
        };
        this.finishOrbit = pauseOrbit();
        canvas.setPointerCapture(event.pointerId);
      },
      { capture: true, signal },
    );
    canvas.addEventListener(
      "pointermove",
      (event) => {
        const drag = this.drag;
        if (!drag || drag.pointer !== event.pointerId) return;
        consume(event);
        const position: Position = [...drag.position];
        if (drag.horizontal) {
          const point = terrainHorizontalPoint(
            this.localRay(ray(event.clientX, event.clientY)),
            drag.mode.camera,
            position[2],
          );
          if (!point || !drag.start) return;
          position[0] += point[0] - drag.start[0];
          position[1] += point[1] - drag.start[1];
        } else position[2] += (drag.startY - event.clientY) * drag.unitsPerPixel;
        const grid = moveTerrainVertex(drag.mode.grid, drag.id, position);
        if (!grid) return;
        drag.grid = grid;
        drag.moved = position.some((v, i) => Math.abs(v - drag.position[i]!) > 0.01);
        this.preview(grid);
        this.draw(grid);
      },
      { capture: true, signal },
    );
    canvas.addEventListener(
      "pointerup",
      (event) => {
        const drag = this.drag;
        if (!drag || drag.pointer !== event.pointerId) return;
        consume(event);
        this.release();
        this.preview(null);
        this.draw(this.mode?.grid ?? null);
        if (drag.moved) drag.mode.commit(drag.grid);
      },
      { capture: true, signal },
    );
    for (const name of ["pointercancel", "lostpointercapture"])
      canvas.addEventListener(
        name,
        (event) => {
          if ((event as PointerEvent).pointerId === this.drag?.pointer) this.cancel();
        },
        { capture: true, signal },
      );
    window.addEventListener(
      "keydown",
      (event) => {
        if (event.key === "Escape" && this.drag) {
          consume(event);
          this.cancel();
        }
      },
      { capture: true, signal },
    );
    window.addEventListener("blur", () => this.cancel(), { signal });
    signal.addEventListener("abort", () => this.cancel(), { once: true });
  }
  dispose() {
    this.setMode(null);
    disposeObjectResources([this.root]);
    this.root.clear();
  }
}
