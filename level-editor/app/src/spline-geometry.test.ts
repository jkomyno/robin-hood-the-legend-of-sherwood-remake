import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { parseLevel3D, type LevelSpline, type Level3D } from "@rle/shared";
import { riverGeometry, splineCurve, wallMesh } from "./spline-geometry.ts";
import { SplineLayer } from "./spline-layer.ts";

const camera = { kind: "oblique-orthographic" as const, elevation_deg: 35 };
const river: LevelSpline = { id: "river", name: "River", kind: "river", points: [[0,0,0],[300,0,0],[600,150,0]],
  width: 80, repeatLength: 100, closed: false };
test("river ribbons keep world width and repeat texture by arc length through curves", () => {
  const geometry = riverGeometry(river, camera), positions = geometry.getAttribute("position"), uv = geometry.getAttribute("uv");
  for (let i = 0; i < positions.count; i += 2) {
    assert.ok(Math.abs(new THREE.Vector3().fromBufferAttribute(positions, i).distanceTo(
      new THREE.Vector3().fromBufferAttribute(positions, i + 1)) - 80) < 0.001);
  }
  assert.ok(Math.abs(uv.getY(uv.count - 1) - splineCurve(river, camera).getLength() / 100) < 1e-5);
  geometry.dispose();
});
test("wall repeats bend real mesh vertices, retain UVs and leave shared geometry untouched", () => {
  const source = new THREE.Mesh(new THREE.BoxGeometry(100, 12, 40), new THREE.MeshBasicMaterial());
  const original = Array.from(source.geometry.getAttribute("position").array);
  const path: LevelSpline = { ...river, kind: "wall", asset: "wall", axis: "x", width: 12, repeatLength: 100 };
  const wall = wallMesh(path, camera, new Map([["asset:wall:building-000", source]]));
  assert.ok(wall.children.length >= 6);
  const last = wall.children.at(-1) as THREE.Mesh;
  const end = new THREE.Box3().setFromObject(last);
  assert.ok(end.max.x > 590 && end.min.y < -200, "last section must follow the curved endpoint");
  assert.ok(last.geometry.getAttribute("uv").count > 0);
  assert.deepEqual(Array.from(source.geometry.getAttribute("position").array), original);
  wall.traverse(node => { if (node instanceof THREE.Mesh) node.geometry.dispose(); });
  source.geometry.dispose(); (source.material as THREE.Material).dispose();
});
test("a skewed source wall keeps its requested thickness instead of its bounding-box ratio", () => {
  const source = new THREE.Mesh(new THREE.BoxGeometry(100, 12, 40), new THREE.MeshBasicMaterial());
  const positions = source.geometry.getAttribute("position");
  for (let i = 0; i < positions.count; i++) positions.setY(i, positions.getY(i) + positions.getX(i) * 0.6);
  const path: LevelSpline = { ...river, kind: "wall", asset: "wall", axis: "x", width: 30,
    repeatLength: 100, points: [[0,0,0],[200,0,0]] };
  const wall = wallMesh(path, camera, new Map([["asset:wall:building-000", source]]));
  for (const child of wall.children) {
    const bounds = new THREE.Box3().setFromObject(child);
    assert.ok(Math.abs(bounds.max.y - bounds.min.y - 30) < 0.001);
  }
  wall.traverse(node => { if (node instanceof THREE.Mesh) node.geometry.dispose(); });
  source.geometry.dispose(); source.material.dispose();
});
test("spline geometry retirement does not dispose borrowed wall materials or source meshes", () => {
  const source = new THREE.Mesh(new THREE.BoxGeometry(100, 12, 40), new THREE.MeshBasicMaterial());
  let sourceDisposals = 0;
  source.geometry.addEventListener("dispose", () => sourceDisposals++);
  source.material.addEventListener("dispose", () => sourceDisposals++);
  const layer = new SplineLayer();
  const path: LevelSpline = { ...river, kind: "wall", asset: "wall", axis: "x", width: 12, repeatLength: 100 };
  layer.sync([path], camera, new Map([["asset:wall:building-000", source]]));
  layer.clear();
  assert.equal(sourceDisposals, 0);
  source.geometry.dispose(); source.material.dispose();
});
test("documents round-trip splines and reject dangling sources and invalid control geometry", () => {
  const document: Level3D = { version: 1, map: "Test", glb: "map.glb", size: [1000,1000], camera, objects: [], groups: [], splines: [river] };
  assert.deepEqual(parseLevel3D(JSON.parse(JSON.stringify(document))).splines, [river]);
  assert.throws(() => parseLevel3D({ ...document, splines: [{ ...river, width: 0 }] }), /width/);
  assert.throws(() => parseLevel3D({ ...document, splines: [{ ...river, points: [[0,0,0]] }] }), /control points/);
  assert.throws(() => parseLevel3D({ ...document, splines: [{ ...river, kind: "wall", asset: "missing", axis: "x" }] }), /wall asset/);
});
