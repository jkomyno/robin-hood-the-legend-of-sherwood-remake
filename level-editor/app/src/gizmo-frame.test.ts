import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { centerGizmoFrame, moveFromGizmoFrame } from "./gizmo-frame.ts";

test("rotated gizmo stays centered on offset geometry and translates through transformed parents", () => {
  const scene = new THREE.Scene();
  const parent = new THREE.Group();
  parent.rotation.set(-Math.PI / 2, 0, Math.PI / 6);
  parent.position.set(300, 20, -150);
  scene.add(parent);
  const object = new THREE.Group();
  object.position.set(30, 40, 50);
  parent.add(object);
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(10, 20, 30));
  mesh.position.set(400, -200, 80);
  object.add(mesh);
  const frame = new THREE.Object3D();
  frame.rotation.y = Math.PI / 4;
  scene.add(frame);
  const offset = new THREE.Vector3();
  centerGizmoFrame(object, frame, offset);
  const center = new THREE.Box3().setFromObject(object, true).getCenter(new THREE.Vector3());
  assert.ok(frame.position.distanceTo(center) < 1e-9);
  const originalPosition = object.position.clone();
  moveFromGizmoFrame(object, frame, offset);
  assert.ok(
    object.position.distanceTo(originalPosition) < 1e-9,
    "attaching must not move the asset",
  );
  const delta = new THREE.Vector3(20, 0, 0).applyQuaternion(frame.quaternion);
  frame.position.add(delta);
  moveFromGizmoFrame(object, frame, offset);
  object.updateWorldMatrix(true, true);
  const movedCenter = new THREE.Box3().setFromObject(object, true).getCenter(new THREE.Vector3());
  assert.ok(movedCenter.distanceTo(center.add(delta)) < 1e-9);
  assert.equal(object.rotation.y, 0, "gizmo rotation must not rotate the asset");
  centerGizmoFrame(object, frame, offset);
  assert.ok(frame.position.distanceTo(movedCenter) < 1e-9);
});
