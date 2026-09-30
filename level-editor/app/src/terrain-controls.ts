import * as THREE from "three";
import {
  cellTriangles,
  gameToScene,
  validateTerrainGrid,
  type TerrainGrid,
  type MapCamera,
} from "@rle/shared";
import { disposeObjectResources } from "./resources.ts";

type Position = [number, number, number];
type ScreenPoint = { x: number; y: number };
export interface TerrainEditMode {
  grid: TerrainGrid;
  camera: MapCamera;
  selectedVertices?: string[];
  selectVertices?(ids: string[]): void;
  selectedCells?: string[];
  selectCells?(ids: string[]): void;
  /** Compatibility with callers that expose a single vertex. */
  selectedVertex?: string;
  selectVertex?(id: string): void;
  commit(grid: TerrainGrid): void;
  deselect?(): void;
}
const validatedGrids = new WeakSet<TerrainGrid>();

/** Apply one translation atomically; adjacent selected vertices may move together. */
export function moveTerrainVertices(
  grid: TerrainGrid,
  ids: readonly string[],
  delta: Position,
): TerrainGrid | null {
  const selected = new Set(ids);
  const known = new Set(grid.vertices.map((v) => v.id));
  for (const id of selected) if (!known.has(id)) throw new Error(`Unknown terrain vertex: ${id}`);
  if (!delta.every(Number.isFinite)) return null;
  if (!selected.size) return grid;
  try {
    if (!validatedGrids.has(grid)) {
      validateTerrainGrid(grid);
      validatedGrids.add(grid);
    }
    const vertices = grid.vertices.map((v) =>
      selected.has(v.id)
        ? { ...v, position: v.position.map((p, i) => p + delta[i]!) as Position }
        : v,
    );
    if (vertices.some((v) => !v.position.every(Number.isFinite))) return null;
    const next = { ...grid, vertices };
    // A height-only translation cannot alter ground topology. Horizontal motion
    // validates the whole result, including distant boundary intersections.
    if (delta[0] !== 0 || delta[1] !== 0) validateTerrainGrid(next);
    validatedGrids.add(next);
    return next;
  } catch {
    return null;
  }
}
export function moveTerrainVertex(
  grid: TerrainGrid,
  id: string,
  position: Position,
): TerrainGrid | null {
  const vertex = grid.vertices.find((v) => v.id === id);
  if (!vertex) throw new Error(`Unknown terrain vertex: ${id}`);
  return moveTerrainVertices(
    grid,
    [id],
    position.map((p, i) => p - vertex.position[i]!) as Position,
  );
}
export function terrainVertexFromHit(
  hit: THREE.Intersection,
  grid: TerrainGrid,
): string | undefined {
  if (typeof hit.object.userData.terrainVertex === "string")
    return hit.object.userData.terrainVertex;
  if (hit.index !== undefined && Array.isArray(hit.object.userData.terrainVertexIds))
    return hit.object.userData.terrainVertexIds[hit.index];
  if (hit.object.userData.terrainVertices && hit.index !== undefined)
    return grid.vertices[hit.index]?.id;
  return undefined;
}
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

type Target = { ids: string[]; kind: "vertex" | "edge" | "cell" };
type Gesture = {
  mode: TerrainEditMode;
  pointer: number;
  kind: "move" | "box" | "toggle";
  ids: string[];
  before: string[];
  startScreen: ScreenPoint;
  start: Position | null;
  height: number;
  unitsPerPixel: number;
  horizontal: boolean;
  additive: boolean;
  grid: TerrainGrid;
  moved: boolean;
};

/** Transient multi-selection handles. A completed move creates exactly one edit. */
export class TerrainControls {
  readonly root = new THREE.Group();
  private mode: TerrainEditMode | null = null;
  private drag: Gesture | null = null;
  private selection: string[] = [];
  private hover: string[] = [];
  private canvas: HTMLCanvasElement | null = null;
  private finishOrbit: (() => void) | null = null;
  private marquee: HTMLDivElement | null = null;
  private project: ((point: THREE.Vector3) => ScreenPoint | null) | undefined;
  private preview: (grid: TerrainGrid | null) => void;
  constructor(preview: (grid: TerrainGrid | null) => void) {
    this.preview = preview;
    this.root.renderOrder = 1100;
  }
  setMode(mode: TerrainEditMode | null) {
    if (
      this.drag &&
      (!mode ||
        mode.grid !== this.drag.mode.grid ||
        mode.camera.elevation_deg !== this.drag.mode.camera.elevation_deg)
    )
      this.cancel();
    this.mode = mode;
    this.selection =
      mode?.selectedVertices?.slice() ?? (mode?.selectedVertex ? [mode.selectedVertex] : []);
    const known = new Set(mode?.grid.vertices.map((v) => v.id) ?? []);
    this.selection = this.selection.filter((id) => known.has(id));
    this.hover = [];
    this.draw(this.drag?.kind === "move" ? this.drag.grid : (mode?.grid ?? null));
  }
  show(grid: TerrainGrid | null) {
    this.draw(grid);
  }
  private draw(grid: TerrainGrid | null) {
    disposeObjectResources([this.root]);
    this.root.clear();
    this.root.userData.terrainHoverVertices = [...this.hover];
    if (!grid || !this.mode) return;
    const points = grid.vertices.map(
      (v) => new THREE.Vector3(...gameToScene(this.mode!.camera, ...v.position)),
    );
    const selected = new Set(this.selection),
      hovered = new Set(this.hover);
    const color = (id: string) =>
      hovered.has(id)
        ? new THREE.Color(0x68efff)
        : selected.has(id)
          ? new THREE.Color(0xffffff)
          : new THREE.Color(0xffd36b);
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    geometry.setAttribute(
      "color",
      new THREE.Float32BufferAttribute(
        grid.vertices.flatMap((v) => color(v.id).toArray()),
        3,
      ),
    );
    const handles = new THREE.Points(
      geometry,
      new THREE.PointsMaterial({
        vertexColors: true,
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
    const highlights = grid.vertices
      .map((v, i) => ({ id: v.id, point: points[i]! }))
      .filter((v) => selected.has(v.id) || hovered.has(v.id));
    if (highlights.length) {
      const g = new THREE.BufferGeometry().setFromPoints(highlights.map((v) => v.point));
      g.setAttribute(
        "color",
        new THREE.Float32BufferAttribute(
          highlights.flatMap((v) => color(v.id).toArray()),
          3,
        ),
      );
      const overlay = new THREE.Points(
        g,
        new THREE.PointsMaterial({
          vertexColors: true,
          size: 12,
          sizeAttenuation: false,
          depthTest: false,
          depthWrite: false,
        }),
      );
      overlay.userData.terrainVertexIds = highlights.map((v) => v.id);
      overlay.userData.noSunShadow = true;
      overlay.renderOrder = 1102;
      this.root.add(overlay);
    }
    const seen = new Set<string>(),
      edges: [number, number][] = [],
      segments: THREE.Vector3[] = [],
      edgeColors: number[] = [];
    for (const cell of grid.cells)
      for (let i = 0; i < cell.vertices.length; i++) {
        const a = cell.vertices[i]!,
          b = cell.vertices[(i + 1) % cell.vertices.length]!,
          key = `${Math.min(a, b)}/${Math.max(a, b)}`;
        if (seen.has(key)) continue;
        seen.add(key);
        edges.push([a, b]);
        segments.push(points[a]!, points[b]!);
        const strong = hovered.has(grid.vertices[a]!.id) && hovered.has(grid.vertices[b]!.id);
        const c = new THREE.Color(
          strong
            ? 0x68efff
            : selected.has(grid.vertices[a]!.id) && selected.has(grid.vertices[b]!.id)
              ? 0xffffff
              : 0xb29a57,
        );
        edgeColors.push(...c.toArray(), ...c.toArray());
      }
    const lineGeometry = new THREE.BufferGeometry().setFromPoints(segments);
    lineGeometry.setAttribute("color", new THREE.Float32BufferAttribute(edgeColors, 3));
    const line = new THREE.LineSegments(
      lineGeometry,
      new THREE.LineBasicMaterial({ vertexColors: true, depthTest: false, depthWrite: false }),
    );
    line.userData.terrainEdges = edges;
    line.userData.noSunShadow = true;
    line.renderOrder = 1100;
    this.root.add(line);
    const indices: number[] = [],
      cells: string[] = [];
    for (const cell of grid.cells)
      for (const triangle of cellTriangles(grid, cell)) {
        indices.push(...triangle);
        cells.push(cell.id);
      }
    const cellGeometry = new THREE.BufferGeometry().setFromPoints(points);
    cellGeometry.setIndex(indices);
    const surface = new THREE.Mesh(
      cellGeometry,
      new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, visible: false, depthWrite: false }),
    );
    surface.userData.terrainPickCells = cells;
    surface.userData.noSunShadow = true;
    this.root.add(surface);
    this.root.updateWorldMatrix(true, true);
  }
  private localRay(ray: THREE.Raycaster) {
    this.root.updateWorldMatrix(true, false);
    return ray.ray.clone().applyMatrix4(new THREE.Matrix4().copy(this.root.matrixWorld).invert());
  }
  private select(ids: string[]) {
    const mode = this.mode;
    if (!mode) return;
    this.selection = [...new Set(ids)];
    const selected = new Set(this.selection);
    const cells = mode.grid.cells
      .filter((c) => c.vertices.every((i) => selected.has(mode.grid.vertices[i]!.id)))
      .map((c) => c.id);
    mode.selectVertices?.([...this.selection]);
    if (!mode.selectVertices) mode.selectVertex?.(this.selection[0] ?? "");
    mode.selectCells?.(cells);
    if (!this.selection.length) mode.deselect?.();
    this.draw(mode.grid);
  }
  private movingIds(target: Target) {
    const selected = new Set(this.selection);
    return target.ids.every((id) => selected.has(id)) ? [...this.selection] : target.ids;
  }
  private setHover(ids: string[], grid = this.mode?.grid) {
    if (ids.length === this.hover.length && ids.every((id, i) => id === this.hover[i])) return;
    this.hover = ids;
    this.draw(grid ?? null);
  }
  private pick(
    x: number,
    y: number,
    ray: (x: number, y: number) => THREE.Raycaster,
  ): Target | null {
    const mode = this.mode;
    if (!mode) return null;
    const pick = ray(x, y),
      handles = this.root.children.find((o) => o instanceof THREE.Points) as
        | THREE.Points
        | undefined;
    if (!handles) return null;
    handles.geometry.computeBoundingSphere();
    const centre = handles.geometry
      .boundingSphere!.center.clone()
      .applyMatrix4(handles.matrixWorld);
    const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(pick.ray.direction, centre);
    const a = pick.ray.intersectPlane(plane, new THREE.Vector3()),
      b = ray(x, y + 1).ray.intersectPlane(plane, new THREE.Vector3());
    const pointThreshold = pick.params.Points.threshold,
      lineThreshold = pick.params.Line.threshold;
    if (a && b) {
      pick.params.Points.threshold = a.distanceTo(b) * 6;
      pick.params.Line.threshold = a.distanceTo(b) * 4;
    }
    const hits = pick.intersectObject(this.root, true);
    pick.params.Points.threshold = pointThreshold;
    pick.params.Line.threshold = lineThreshold;
    const vertex = hits.find((h) => terrainVertexFromHit(h, mode.grid) !== undefined);
    if (vertex) return { ids: [terrainVertexFromHit(vertex, mode.grid)!], kind: "vertex" };
    const edge = hits.find((h) => h.object.userData.terrainEdges && h.index !== undefined);
    if (edge) {
      const indices = edge.object.userData.terrainEdges[Math.floor(edge.index! / 2)] as
        | [number, number]
        | undefined;
      if (indices) return { ids: indices.map((i) => mode.grid.vertices[i]!.id), kind: "edge" };
    }
    const cellHit = hits.find(
      (h) => h.object.userData.terrainPickCells && h.faceIndex !== undefined,
    );
    if (!cellHit) return null;
    const id = cellHit.object.userData.terrainPickCells[cellHit.faceIndex!];
    const cell = mode.grid.cells.find((c) => c.id === id);
    return cell ? { ids: cell.vertices.map((i) => mode.grid.vertices[i]!.id), kind: "cell" } : null;
  }
  private boxIds(start: ScreenPoint, end: ScreenPoint) {
    if (!this.mode || !this.project) return [];
    this.root.updateWorldMatrix(true, false);
    const minX = Math.min(start.x, end.x),
      maxX = Math.max(start.x, end.x),
      minY = Math.min(start.y, end.y),
      maxY = Math.max(start.y, end.y);
    return this.mode.grid.vertices
      .filter((v) => {
        const p = this.project!(
          new THREE.Vector3(...gameToScene(this.mode!.camera, ...v.position)).applyMatrix4(
            this.root.matrixWorld,
          ),
        );
        return p && p.x >= minX && p.x <= maxX && p.y >= minY && p.y <= maxY;
      })
      .map((v) => v.id);
  }
  private drawMarquee(start: ScreenPoint, end: ScreenPoint) {
    if (!this.marquee && this.canvas?.ownerDocument?.body) {
      this.marquee = this.canvas.ownerDocument.createElement("div");
      this.marquee.style.cssText =
        "position:fixed;pointer-events:none;z-index:100000;border:1px solid #68efff;background:#68efff22;";
      this.canvas.ownerDocument.body.appendChild(this.marquee);
    }
    if (this.marquee)
      Object.assign(this.marquee.style, {
        left: `${Math.min(start.x, end.x)}px`,
        top: `${Math.min(start.y, end.y)}px`,
        width: `${Math.abs(end.x - start.x)}px`,
        height: `${Math.abs(end.y - start.y)}px`,
      });
  }
  private release() {
    const pointer = this.drag?.pointer;
    this.drag = null;
    this.marquee?.remove();
    this.marquee = null;
    if (pointer !== undefined && this.canvas?.hasPointerCapture(pointer))
      this.canvas.releasePointerCapture(pointer);
    this.finishOrbit?.();
    this.finishOrbit = null;
  }
  cancel() {
    if (!this.drag) return;
    this.release();
    this.hover = [];
    this.preview(null);
    this.draw(this.mode?.grid ?? null);
  }
  setup(
    canvas: HTMLCanvasElement,
    ray: (x: number, y: number) => THREE.Raycaster,
    pauseOrbit: () => () => void,
    signal: AbortSignal,
    project?: (point: THREE.Vector3) => ScreenPoint | null,
  ) {
    this.canvas = canvas;
    this.project = project;
    const consume = (event: Event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    canvas.addEventListener(
      "pointerdown",
      (event) => {
        if (!this.mode || this.drag || (event.button !== 0 && event.button !== 2)) return;
        const mode = this.mode,
          screen = { x: event.clientX, y: event.clientY },
          before = [...this.selection];
        if (event.button === 2) {
          consume(event);
          this.drag = {
            mode,
            pointer: event.pointerId,
            kind: "box",
            ids: [],
            before,
            startScreen: screen,
            start: null,
            height: 0,
            unitsPerPixel: 0,
            horizontal: false,
            additive: event.shiftKey,
            grid: mode.grid,
            moved: false,
          };
          this.drawMarquee(screen, screen);
        } else {
          const target = this.pick(event.clientX, event.clientY, ray);
          if (!target) {
            if (!event.shiftKey) this.select([]);
            this.setHover([]);
            return;
          }
          consume(event);
          if (event.shiftKey) {
            const selected = new Set(before),
              all = target.ids.every((id) => selected.has(id));
            for (const id of target.ids)
              if (all) selected.delete(id);
              else selected.add(id);
            this.select([...selected]);
            this.drag = {
              mode,
              pointer: event.pointerId,
              kind: "toggle",
              ids: [],
              before,
              startScreen: screen,
              start: null,
              height: 0,
              unitsPerPixel: 0,
              horizontal: false,
              additive: false,
              grid: mode.grid,
              moved: false,
            };
          } else {
            const ids = this.movingIds(target);
            const positions = mode.grid.vertices.filter((v) => ids.includes(v.id));
            const position = positions.reduce(
              (p, v) => p.map((n, i) => n + v.position[i]! / positions.length) as Position,
              [0, 0, 0] as Position,
            );
            const local = this.localRay(ray(event.clientX, event.clientY)),
              start = terrainHorizontalPoint(local, mode.camera, position[2]);
            const horizontal = event.altKey;
            if (horizontal && !start) return;
            const point = new THREE.Vector3(...gameToScene(mode.camera, ...position)),
              plane = new THREE.Plane().setFromNormalAndCoplanarPoint(local.direction, point);
            const a = local.intersectPlane(plane, new THREE.Vector3()),
              b = this.localRay(ray(event.clientX, event.clientY + 1)).intersectPlane(
                plane,
                new THREE.Vector3(),
              );
            if (!a || !b) return;
            this.select(ids);
            this.drag = {
              mode,
              pointer: event.pointerId,
              kind: "move",
              ids,
              before,
              startScreen: screen,
              start,
              height: position[2],
              unitsPerPixel:
                a.distanceTo(b) * Math.cos((mode.camera.elevation_deg * Math.PI) / 180),
              horizontal,
              additive: false,
              grid: mode.grid,
              moved: false,
            };
            this.setHover(ids);
          }
        }
        this.finishOrbit = pauseOrbit();
        canvas.setPointerCapture(event.pointerId);
      },
      { capture: true, signal },
    );
    canvas.addEventListener(
      "pointermove",
      (event) => {
        const drag = this.drag;
        if (!drag) {
          if (this.mode) {
            const target = this.pick(event.clientX, event.clientY, ray);
            this.setHover(target ? this.movingIds(target) : []);
          }
          return;
        }
        if (drag.pointer !== event.pointerId) return;
        consume(event);
        if (drag.kind === "toggle") return;
        if (drag.kind === "box") {
          const end = { x: event.clientX, y: event.clientY },
            inside = this.boxIds(drag.startScreen, end);
          drag.ids = drag.additive ? [...new Set([...drag.before, ...inside])] : inside;
          drag.moved = Math.hypot(end.x - drag.startScreen.x, end.y - drag.startScreen.y) > 2;
          this.drawMarquee(drag.startScreen, end);
          this.setHover(drag.ids);
          return;
        }
        const delta: Position = [0, 0, 0];
        if (drag.horizontal) {
          const point = terrainHorizontalPoint(
            this.localRay(ray(event.clientX, event.clientY)),
            drag.mode.camera,
            drag.height,
          );
          if (!point || !drag.start) return;
          delta[0] = point[0] - drag.start[0];
          delta[1] = point[1] - drag.start[1];
        } else delta[2] = (drag.startScreen.y - event.clientY) * drag.unitsPerPixel;
        const next = moveTerrainVertices(drag.mode.grid, drag.ids, delta);
        if (!next) return;
        drag.grid = next;
        drag.moved = delta.some((n) => Math.abs(n) > 0.01);
        this.preview(next);
        this.draw(next);
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
        if (drag.kind === "box") {
          const inside = this.boxIds(drag.startScreen, { x: event.clientX, y: event.clientY });
          this.select(drag.additive ? [...new Set([...drag.before, ...inside])] : inside);
        }
        this.preview(null);
        this.hover = [];
        this.draw(this.mode?.grid ?? null);
        if (drag.kind === "move" && drag.moved) drag.mode.commit(drag.grid);
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
    canvas.addEventListener(
      "pointerleave",
      () => {
        if (!this.drag) this.setHover([]);
      },
      { signal },
    );
    for (const name of ["click", "dblclick", "contextmenu"])
      canvas.addEventListener(
        name,
        (event) => {
          if (this.mode) consume(event);
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
