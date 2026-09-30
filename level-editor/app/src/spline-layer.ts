import * as THREE from "three";
import {
  gameToScene,
  type LevelSpline,
  type Level3D,
  type MapCamera,
  type Vec3,
} from "@rle/shared";
import { riverMesh, splineCurve, wallMesh } from "./spline-geometry.ts";
import { disposeObjectResources } from "./resources.ts";
import { terrainHeightAt } from "../../shared/src/authored-terrain.ts";

export interface SplineEditMode {
  path: LevelSpline;
  drawing: boolean;
  point: number;
  section?: number;
  append(point: Vec3): void;
  move(index: number, point: Vec3): void;
  selectPoint(index: number): void;
  selectSection?(index: number): void;
}

export class SplineLayer {
  assetObjects(): THREE.Object3D[] {
    return [...this.views.values()]
      .filter((view) => view.path.kind === "wall" && view.object.visible)
      .map((view) => view.object)
      .concat(this.preview?.path.kind === "wall" ? [this.preview.object] : []);
  }
  bakeObjects(): THREE.Object3D[] {
    if (this.mode) throw new Error("Finish editing the path before exporting the map.");
    return [...this.views.values()].map((view) => view.object);
  }
  readonly root = new THREE.Group();
  readonly controls = new THREE.Group();
  private views = new Map<string, { path: LevelSpline; object: THREE.Object3D }>();
  private preview: { path: LevelSpline; object: THREE.Object3D } | null = null;
  private camera: MapCamera = { kind: "oblique-orthographic", elevation_deg: 35 };
  private sources = new Map<string, THREE.Object3D>();
  private mode: SplineEditMode | null = null;
  private document?: Level3D;
  constructor() {
    // Keep editing overlays after transparent path surfaces as well as opaque geometry.
    this.controls.renderOrder = 1000;
    this.root.add(this.controls);
  }
  private release(path: LevelSpline, object: THREE.Object3D) {
    object.removeFromParent();
    if (path.kind !== "wall") disposeObjectResources([object]);
    else
      object.traverse((node) => {
        if (node instanceof THREE.Mesh) node.geometry.dispose();
      });
  }
  private build(path: LevelSpline) {
    return path.kind === "wall"
      ? wallMesh(path, this.camera, this.sources)
      : riverMesh(path, this.camera, this.document);
  }
  sync(
    paths: LevelSpline[],
    camera: MapCamera,
    sources: Map<string, THREE.Object3D>,
    document?: Level3D,
  ) {
    const terrainChanged =
      this.document?.terrain !== document?.terrain ||
      this.document?.splines !== document?.splines ||
      this.document?.camera !== document?.camera ||
      this.document?.customMaterials !== document?.customMaterials;
    this.document = document;
    this.camera = camera;
    this.sources = sources;
    const ids = new Set(paths.map((path) => path.id));
    for (const [id, view] of this.views)
      if (!ids.has(id)) {
        this.release(view.path, view.object);
        this.views.delete(id);
      }
    for (const path of paths) {
      const previous = this.views.get(path.id);
      if (previous?.path === path && !(terrainChanged && path.kind !== "wall")) continue;
      const object = this.build(path);
      if (previous) this.release(previous.path, previous.object);
      this.views.set(path.id, { path, object });
      this.root.add(object);
    }
  }
  setMode(mode: SplineEditMode | null) {
    this.mode = mode;
    this.clearPreview();
    this.refreshControls(mode?.path);
    if (mode?.drawing && mode.path.points.length >= 2) this.showPreview(mode.path);
  }
  showPreview(path: LevelSpline) {
    // A failed replacement must not discard the last valid preview.
    const object = this.build(path);
    this.clearPreview();
    this.root.add(object);
    this.preview = { path, object };
    const original = this.views.get(path.id);
    if (original) original.object.visible = false;
    this.refreshControls(path);
  }
  private clearPreview() {
    if (this.preview) this.release(this.preview.path, this.preview.object);
    this.preview = null;
    for (const view of this.views.values()) view.object.visible = true;
  }
  private refreshControls(path?: LevelSpline) {
    disposeObjectResources([this.controls]);
    this.controls.clear();
    if (!path) return;
    if (path.kind === "road" && this.document) {
      const road = path;
      path = {
        ...road,
        points: road.points.map((point, index) => [
          point[0],
          point[1],
          (terrainHeightAt(this.document!, point[0], point[1]) ?? point[2]) +
            (road.pointHeightOffsets?.[index] ?? 0),
        ]),
      };
    }
    if (path.points.length >= 2) {
      const curve = splineCurve(path, this.camera);
      const count = path.closed ? path.points.length : path.points.length - 1;
      for (let section = 0; section < count; section++) {
        const points = Array.from({ length: 25 }, (_, i) =>
          curve.getPoint((section + i / 24) / count).add(new THREE.Vector3(0, 0, 4)),
        );
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(points),
          new THREE.LineBasicMaterial({
            color: section === this.mode?.section ? 0xffcd59 : 0x77e4e8,
            depthTest: false,
            depthWrite: false,
          }),
        );
        line.userData.splineSection = section;
        line.renderOrder = 102;
        this.controls.add(line);
      }
    }
    path.points.forEach((point, index) => {
      const handle = new THREE.Mesh(
        new THREE.SphereGeometry(9, 10, 8),
        new THREE.MeshBasicMaterial({
          color: index === this.mode?.point ? 0xffcd59 : 0x77e4e8,
          transparent: true,
          depthTest: false,
          depthWrite: false,
        }),
      );
      handle.userData.noSunShadow = true;
      handle.position.set(...gameToScene(this.camera, ...point));
      handle.position.z += 4;
      handle.userData.splinePoint = index;
      handle.renderOrder = 101;
      this.controls.add(handle);
    });
    this.root.updateWorldMatrix(true, true);
  }
  hitHandle(ray: THREE.Raycaster): number | null {
    this.root.updateWorldMatrix(true, true);
    const hit = ray
      .intersectObjects(this.controls.children)
      .find((hit) => typeof hit.object.userData.splinePoint === "number");
    return hit ? hit.object.userData.splinePoint : null;
  }
  hitSection(ray: THREE.Raycaster): number | null {
    this.root.updateWorldMatrix(true, true);
    const previous = ray.params.Line.threshold;
    ray.params.Line.threshold = 8;
    try {
      const hit = ray
        .intersectObjects(this.controls.children)
        .find((hit) => typeof hit.object.userData.splineSection === "number");
      return hit ? hit.object.userData.splineSection : null;
    } finally {
      ray.params.Line.threshold = previous;
    }
  }
  clear() {
    this.setMode(null);
    for (const view of this.views.values()) this.release(view.path, view.object);
    this.views.clear();
    this.sources = new Map();
  }
}
