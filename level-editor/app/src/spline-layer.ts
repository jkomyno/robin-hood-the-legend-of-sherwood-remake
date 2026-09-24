import * as THREE from "three";
import { gameToScene, type LevelSpline, type MapCamera, type Vec3 } from "@rle/shared";
import { riverMesh, splineCurve, wallMesh } from "./spline-geometry.ts";
import { disposeObjectResources } from "./resources.ts";

export interface SplineEditMode {
  path: LevelSpline;
  drawing: boolean;
  point: number;
  append(point: Vec3): void;
  move(index: number, point: Vec3): void;
  selectPoint(index: number): void;
}

export class SplineLayer {
  readonly root = new THREE.Group();
  readonly controls = new THREE.Group();
  private views = new Map<string, { path: LevelSpline; object: THREE.Object3D }>();
  private preview: { path: LevelSpline; object: THREE.Object3D } | null = null;
  private camera: MapCamera = { kind: "oblique-orthographic", elevation_deg: 35 };
  private sources = new Map<string, THREE.Object3D>();
  private mode: SplineEditMode | null = null;
  constructor() { this.root.add(this.controls); }
  private release(path: LevelSpline, object: THREE.Object3D) {
    object.removeFromParent();
    if (path.kind === "river") disposeObjectResources([object]);
    else object.traverse(node => { if (node instanceof THREE.Mesh) node.geometry.dispose(); });
  }
  private build(path: LevelSpline) {
    return path.kind === "river" ? riverMesh(path, this.camera) : wallMesh(path, this.camera, this.sources);
  }
  sync(paths: LevelSpline[], camera: MapCamera, sources: Map<string, THREE.Object3D>) {
    this.camera = camera;
    this.sources = sources;
    const ids = new Set(paths.map(path => path.id));
    for (const [id, view] of this.views) if (!ids.has(id)) {
      this.release(view.path, view.object);
      this.views.delete(id);
    }
    for (const path of paths) {
      const previous = this.views.get(path.id);
      if (previous?.path === path) continue;
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
    this.clearPreview();
    const object = this.build(path);
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
    if (path.points.length >= 2) {
      const points = splineCurve(path, this.camera).getSpacedPoints(128).map(p => p.add(new THREE.Vector3(0, 0, 3)));
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({ color: 0x77e4e8, depthTest: false }));
      line.renderOrder = 100;
      this.controls.add(line);
    }
    path.points.forEach((point, index) => {
      const handle = new THREE.Mesh(new THREE.SphereGeometry(9, 10, 8),
        new THREE.MeshBasicMaterial({ color: index === this.mode?.point ? 0xffcd59 : 0x77e4e8, depthTest: false }));
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
    const hit = ray.intersectObjects(this.controls.children).find(hit => typeof hit.object.userData.splinePoint === "number");
    return hit ? hit.object.userData.splinePoint : null;
  }
  clear() {
    this.setMode(null);
    for (const view of this.views.values()) this.release(view.path, view.object);
    this.views.clear();
    this.sources = new Map();
  }
}
