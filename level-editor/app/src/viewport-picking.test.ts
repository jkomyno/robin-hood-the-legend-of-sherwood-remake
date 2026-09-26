import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { setViewportRay, visibleSurface } from "./viewport-picking.ts";

test("orthographic picking includes the complete signed clipping range", () => {
  const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, -20, 20);
  const material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  const near = new THREE.Mesh(new THREE.PlaneGeometry(5, 5), material);
  const far = new THREE.Mesh(new THREE.PlaneGeometry(5, 5), material);
  near.position.z = 10;
  far.position.z = -10;
  near.updateMatrixWorld();
  far.updateMatrixWorld();
  const ray = new THREE.Raycaster();
  ray.setFromCamera(new THREE.Vector2(), camera);
  assert.equal(
    ray.intersectObjects([near, far])[0].object,
    far,
    "camera-plane rays skip the visible front asset",
  );
  setViewportRay(ray, new THREE.Vector2(), camera);
  assert.equal(ray.intersectObjects([near, far])[0].object, near);
  near.position.z = 21;
  near.updateMatrixWorld();
  assert.equal(
    ray.intersectObjects([near, far])[0].object,
    far,
    "clipped geometry must not steal the hit",
  );
});

test("picking ignores transparent atlas pixels but retains opaque ones and respects UV transforms", () => {
  const texture = new THREE.DataTexture(
    new Uint8Array([255, 255, 255, 255, 255, 255, 255, 0]),
    2,
    1,
  );
  texture.flipY = false;
  const material = new THREE.MeshBasicMaterial({ map: texture, alphaTest: 0.5 });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(), material);
  const hit = (u: number) => ({
    object: mesh,
    uv: new THREE.Vector2(u, 0.5),
    point: new THREE.Vector3(),
    distance: 1,
  });
  assert.equal(visibleSurface(hit(0.25)), true);
  assert.equal(visibleSurface(hit(0.75)), false);
  texture.offset.x = 0.5;
  assert.equal(visibleSurface(hit(0.25)), false);
  material.userData.source_ownership_fill = "synthesized";
  assert.equal(
    visibleSurface(hit(0.25)),
    true,
    "building provenance alpha is not physical transparency",
  );
  material.userData.foliage_physical_opacity = true;
  assert.equal(visibleSurface(hit(0.25)), false, "foliage still uses physical coverage");
  material.alphaTest = 0;
  assert.equal(
    visibleSurface(hit(0.25)),
    true,
    "opaque materials render regardless of texture alpha",
  );
  material.visible = false;
  assert.equal(visibleSurface(hit(0.25)), false);
  texture.dispose();
  mesh.geometry.dispose();
  material.dispose();
});

test("alpha maps and hidden ancestors cannot capture selection", () => {
  const alpha = new THREE.DataTexture(new Uint8Array([255, 0, 255, 255]), 1, 1);
  const material = new THREE.MeshBasicMaterial({ alphaMap: alpha, transparent: true });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(), material);
  const hit = {
    object: mesh,
    uv: new THREE.Vector2(0.5, 0.5),
    point: new THREE.Vector3(),
    distance: 1,
  };
  assert.equal(visibleSurface(hit), false, "alpha maps use their green channel");
  material.alphaMap = null;
  const parent = new THREE.Group();
  parent.add(mesh);
  parent.visible = false;
  assert.equal(visibleSurface(hit), false);
  alpha.dispose();
  mesh.geometry.dispose();
  material.dispose();
});

test("reversed-depth orthographic rays hit the asset at the rendered pixel", () => {
  const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, -20, 20);
  Object.assign(camera, { _reversedDepth: true });
  camera.position.set(12, 18, 26);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  camera.updateProjectionMatrix();
  const local = new THREE.Vector3(3, -2, 10);
  const world = local.clone().applyMatrix4(camera.matrixWorld);
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(1), new THREE.MeshBasicMaterial());
  mesh.position.copy(world);
  mesh.updateMatrixWorld();
  const projected = world.clone().project(camera);
  const ray = new THREE.Raycaster();
  setViewportRay(ray, new THREE.Vector2(projected.x, projected.y), camera);
  assert.equal(ray.intersectObject(mesh)[0]?.object, mesh);
  const origin = ray.ray.origin.clone().applyMatrix4(camera.matrixWorldInverse);
  assert.ok(Math.abs(origin.z + camera.near) < 1e-8);
  mesh.geometry.dispose();
  mesh.material.dispose();
});
