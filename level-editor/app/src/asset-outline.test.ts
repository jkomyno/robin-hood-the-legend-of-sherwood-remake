import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { AssetOutlineRenderer } from "./asset-outline.ts";

function fixture() {
  const scene = new THREE.Scene();
  const root = new THREE.Group();
  scene.add(root);
  const texture = new THREE.Texture();
  const material = new THREE.MeshBasicMaterial({ map: texture, alphaTest: 0.5 });
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(), material);
  root.add(mesh);
  const renders: THREE.Scene[] = [];
  const renderer = {
    autoClear: true,
    target: null as THREE.WebGLRenderTarget | null,
    color: new THREE.Color(0xabcdef),
    alpha: 0.7,
    viewport: new THREE.Vector4(0, 0, 300, 200),
    scissor: new THREE.Vector4(0, 0, 300, 200),
    scissorTest: false,
    getRenderTarget() {
      return this.target;
    },
    setRenderTarget(value: THREE.WebGLRenderTarget | null) {
      this.target = value;
    },
    getDrawingBufferSize(value: THREE.Vector2) {
      return value.set(300, 200);
    },
    getClearColor(value: THREE.Color) {
      return value.copy(this.color);
    },
    getClearAlpha() {
      return this.alpha;
    },
    setClearColor(value: THREE.ColorRepresentation, alpha: number) {
      this.color.set(value);
      this.alpha = alpha;
    },
    getViewport(value: THREE.Vector4) {
      return value.copy(this.viewport);
    },
    setViewport(value: THREE.Vector4) {
      this.viewport.copy(value);
    },
    getScissor(value: THREE.Vector4) {
      return value.copy(this.scissor);
    },
    setScissor(value: THREE.Vector4) {
      this.scissor.copy(value);
    },
    getScissorTest() {
      return this.scissorTest;
    },
    setScissorTest(value: boolean) {
      this.scissorTest = value;
    },
    render(value: THREE.Scene) {
      if (value === scene) assert.equal(root.visible, false);
      renders.push(value);
    },
  };
  const outline = new AssetOutlineRenderer();
  const render = () =>
    outline.render(
      renderer as unknown as THREE.WebGLRenderer,
      scene,
      new THREE.PerspectiveCamera(),
      root,
    );
  return { scene, root, mesh, texture, material, renders, renderer, outline, render };
}

test("outline respects alpha coverage and hidden hierarchy without mutating borrowed resources", () => {
  const f = fixture();
  f.material.userData.foliage_physical_opacity = true;
  const hidden = new THREE.Group();
  hidden.visible = false;
  hidden.add(new THREE.Mesh(new THREE.BoxGeometry(), f.material));
  f.root.add(hidden);
  f.mesh.position.set(2, 3, 4);
  let geometryDisposed = false,
    textureDisposed = false,
    materialDisposed = false;
  f.mesh.geometry.addEventListener("dispose", () => {
    geometryDisposed = true;
  });
  f.texture.addEventListener("dispose", () => {
    textureDisposed = true;
  });
  f.material.addEventListener("dispose", () => {
    materialDisposed = true;
  });
  f.render();
  assert.equal(f.renders.length, 3);
  const mask = f.renders[1]!;
  assert.equal(mask.children.length, 1);
  const proxy = mask.children[0] as THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>;
  assert.equal(proxy.material.alphaTest, 0.5);
  assert.equal(proxy.material.map, f.texture);
  assert.deepEqual(new THREE.Vector3().setFromMatrixPosition(proxy.matrix).toArray(), [2, 3, 4]);
  assert.equal(f.mesh.material, f.material);
  assert.equal(f.root.visible, true);
  let proxyDisposed = false;
  proxy.material.addEventListener("dispose", () => {
    proxyDisposed = true;
  });
  f.outline.dispose();
  assert.equal(proxyDisposed, true);
  assert.equal(geometryDisposed || textureDisposed || materialDisposed, false);
});

test("outline shader keeps physical alpha tests but ignores provenance alpha", () => {
  for (const foliage of [false, true]) {
    const f = fixture();
    f.material.userData.source_ownership_fill = "synthesized";
    f.material.userData.foliage_physical_opacity = foliage;
    f.render();
    const proxy = f.renders[1]!.children[0] as THREE.Mesh;
    const material = proxy.material as THREE.Material;
    const shader = {
      ...THREE.ShaderLib.basic,
      uniforms: {},
    } as THREE.WebGLProgramParametersWithUniforms;
    material.onBeforeCompile(shader, f.renderer as unknown as THREE.WebGLRenderer);
    assert.match(shader.vertexShader, /contourNormal = normalize/);
    assert.match(shader.fragmentShader, /#include <alphatest_fragment>/);
    assert.doesNotMatch(shader.fragmentShader, /#include <opaque_fragment>/);
    assert.equal(shader.fragmentShader.includes("sampledDiffuseColor.a = 1.0"), !foliage);
    f.outline.dispose();
  }
});

test("failed outline pass restores visibility and renderer state", () => {
  const f = fixture();
  f.renderer.render = (scene) => {
    if (scene !== f.scene) throw new Error("GPU failure");
  };
  assert.throws(f.render, /GPU failure/);
  assert.equal(f.root.visible, true);
  assert.equal(f.renderer.target, null);
  assert.equal(f.renderer.color.getHex(), 0xabcdef);
  assert.equal(f.renderer.alpha, 0.7);
  assert.equal(f.renderer.autoClear, true);
  f.outline.dispose();
});

test("multiple asset roots share one mask and restore their individual visibility", () => {
  const f = fixture();
  const wall = new THREE.Mesh(new THREE.BoxGeometry(), f.material);
  const hidden = new THREE.Mesh(new THREE.BoxGeometry(), f.material);
  hidden.visible = false;
  f.scene.add(wall, hidden);
  const render = f.renderer.render.bind(f.renderer);
  f.renderer.render = (scene) => {
    if (scene === f.scene) {
      assert.equal(wall.visible, false);
      assert.equal(hidden.visible, false);
    }
    render(scene);
  };
  f.outline.render(
    f.renderer as unknown as THREE.WebGLRenderer,
    f.scene,
    new THREE.PerspectiveCamera(),
    [f.root, wall, hidden, f.root],
  );
  assert.equal(f.renders[1]!.children.length, 2);
  assert.equal(f.root.visible, true);
  assert.equal(wall.visible, true);
  assert.equal(hidden.visible, false);
  f.renderer.render = () => {
    throw new Error("render failed");
  };
  assert.throws(
    () =>
      f.outline.render(
        f.renderer as unknown as THREE.WebGLRenderer,
        f.scene,
        new THREE.PerspectiveCamera(),
        [f.root, wall, hidden],
      ),
    /render failed/,
  );
  assert.equal(f.root.visible, true);
  assert.equal(wall.visible, true);
  assert.equal(hidden.visible, false);
  f.outline.dispose();
});
