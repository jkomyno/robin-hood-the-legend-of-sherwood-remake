import * as THREE from "three";
import { gameToScene, type GroundRegion, type MapCamera } from "@rle/shared";
import { disposeObjectResources } from "./resources.ts";

export interface TerrainEditMode {
  region: GroundRegion;
  camera: MapCamera;
  commit(region: GroundRegion): void;
  deselect?(): void;
}
export function terrainCorners([x, y, w, h]: GroundRegion["bounds"]): [number, number][] {
  return [
    [x, y],
    [x + w, y],
    [x + w, y + h],
    [x, y + h],
  ];
}
export function resizeTerrainCorner(
  bounds: GroundRegion["bounds"],
  corner: number,
  point: [number, number],
): GroundRegion["bounds"] {
  const opposite = terrainCorners(bounds)[(corner + 2) % 4]!;
  const original = terrainCorners(bounds)[corner]!;
  const clamped = point.map((v, i) =>
    Math.abs(v - opposite[i]!) < 1 ? opposite[i]! + (original[i]! < opposite[i]! ? -1 : 1) : v,
  );
  return [
    Math.min(opposite[0], clamped[0]!),
    Math.min(opposite[1], clamped[1]!),
    Math.abs(opposite[0] - clamped[0]!),
    Math.abs(opposite[1] - clamped[1]!),
  ];
}

/** Transient handles and preview; the document owner commits once on release. */
export class TerrainControls {
  readonly root = new THREE.Group();
  private mode: TerrainEditMode | null = null;
  private drag: {
    mode: TerrainEditMode;
    corner: number;
    pointer: number;
    start: [number, number];
    bounds: GroundRegion["bounds"];
    moved: boolean;
  } | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private finishOrbit: (() => void) | null = null;
  private preview: (region: GroundRegion | null) => void;
  constructor(preview: (region: GroundRegion | null) => void) {
    this.preview = preview;
    this.root.renderOrder = 1100;
  }
  setMode(mode: TerrainEditMode | null) {
    this.cancel();
    this.mode = mode;
    this.draw(mode?.region ?? null);
  }
  show(region: GroundRegion | null) {
    this.draw(region);
  }
  private draw(region: GroundRegion | null) {
    disposeObjectResources([this.root]);
    this.root.clear();
    if (!region || !this.mode) return;
    const points = terrainCorners(region.bounds).map(
      ([x, y]) => new THREE.Vector3(...gameToScene(this.mode!.camera, x, y, region.height)),
    );
    const material = new THREE.MeshBasicMaterial({
      color: 0xffd36b,
      depthTest: false,
      depthWrite: false,
      transparent: true,
    });
    const geometry = new THREE.SphereGeometry(10, 12, 8);
    points.forEach((p, i) => {
      const handle = new THREE.Mesh(geometry, material);
      handle.position.copy(p);
      handle.renderOrder = 1101;
      handle.userData.terrainCorner = i;
      handle.userData.noSunShadow = true;
      this.root.add(handle);
    });
    const line = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(points),
      new THREE.LineBasicMaterial({
        color: 0xffd36b,
        depthTest: false,
        depthWrite: false,
        transparent: true,
      }),
    );
    line.renderOrder = 1100;
    this.root.add(line);
    this.root.updateWorldMatrix(true, true);
  }
  private point(ray: THREE.Raycaster, mode: TerrainEditMode): [number, number] | null {
    this.root.updateWorldMatrix(true, false);
    const local = ray.ray
      .clone()
      .applyMatrix4(new THREE.Matrix4().copy(this.root.matrixWorld).invert());
    const z = gameToScene(mode.camera, 0, 0, mode.region.height)[2];
    if (Math.abs(local.direction.z) < 1e-8) return null;
    const point = local.at((z - local.origin.z) / local.direction.z, new THREE.Vector3());
    return [point.x, -point.y * Math.sin((mode.camera.elevation_deg * Math.PI) / 180)];
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
    this.draw(this.mode?.region ?? null);
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
        const pick = ray(event.clientX, event.clientY);
        const hit = pick
          .intersectObject(this.root, true)
          .find((h) => typeof h.object.userData.terrainCorner === "number");
        if (!hit) return;
        const start = this.point(pick, this.mode);
        if (!start) return;
        consume(event);
        this.drag = {
          mode: this.mode,
          corner: hit.object.userData.terrainCorner,
          pointer: event.pointerId,
          start,
          bounds: this.mode.region.bounds,
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
        const p = this.point(ray(event.clientX, event.clientY), drag.mode);
        if (!p) return;
        const corner = terrainCorners(drag.mode.region.bounds)[drag.corner]!;
        drag.bounds = resizeTerrainCorner(drag.mode.region.bounds, drag.corner, [
          corner[0] + p[0] - drag.start[0],
          corner[1] + p[1] - drag.start[1],
        ]);
        drag.moved = drag.bounds.some((v, i) => Math.abs(v - drag.mode.region.bounds[i]!) > 0.01);
        const region = { ...drag.mode.region, bounds: drag.bounds };
        this.preview(region);
        this.draw(region);
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
        this.draw(this.mode?.region ?? null);
        if (drag.moved) drag.mode.commit({ ...drag.mode.region, bounds: drag.bounds });
      },
      { capture: true, signal },
    );
    for (const event of ["pointercancel", "lostpointercapture"])
      canvas.addEventListener(event, () => this.cancel(), { capture: true, signal });
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
  }
  dispose() {
    this.setMode(null);
    disposeObjectResources([this.root]);
    this.root.clear();
  }
}
