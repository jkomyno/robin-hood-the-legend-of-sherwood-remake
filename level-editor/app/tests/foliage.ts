import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { TextureDisplay } from "../src/texture-display";

/** Run against the real GLB produced by test_foliage_export.py, not a mock loader. */
async function run() {
  const fixture = new URLSearchParams(location.search).get("fixture");
  if (!fixture) throw new Error("Expected ?fixture=<exported foliage GLB URL>");
  const { scene: asset } = await new GLTFLoader().loadAsync(fixture);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xff00ff);
  scene.add(asset);
  const display = new TextureDisplay();
  display.smooth = false;
  display.apply(asset);
  scene.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(asset),
    center = box.getCenter(new THREE.Vector3());
  const camera = new THREE.OrthographicCamera(-1.5, 1.5, 1.5, -1.5, 0.01, 20);
  const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
  renderer.setSize(128, 128);
  renderer.setPixelRatio(1);
  const target = new THREE.WebGLRenderTarget(128, 128);
  const pixels = new Uint8Array(128 * 128 * 4);
  const results: { name: string; mask: boolean[]; covered: number; mean: number[] }[] = [];
  const check = (condition: boolean, message: string) => {
    if (!condition) throw new Error(message);
  };
  for (const backside of [false, true])
    for (const synthesized of [true, false]) {
      display.synthesized.value = synthesized;
      camera.position.copy(center).add(new THREE.Vector3(0, 0, backside ? -5 : 5));
      camera.lookAt(center);
      camera.updateMatrixWorld(true);
      renderer.setRenderTarget(target);
      renderer.render(scene, camera);
      renderer.readRenderTargetPixels(target, 0, 0, 128, 128, pixels);
      const mask: boolean[] = [],
        sum = [0, 0, 0];
      for (let i = 0; i < pixels.length; i += 4) {
        const covered = !(pixels[i]! > 245 && pixels[i + 1]! < 10 && pixels[i + 2]! > 245);
        mask.push(covered);
        if (covered) for (let c = 0; c < 3; c++) sum[c]! += pixels[i + c]!;
      }
      const covered = mask.filter(Boolean).length;
      check(covered > 1000 && covered < 5000, `Cutout lost: ${covered} pixels`);
      results.push({
        name: `${backside ? "back" : "front"}-${synthesized ? "normal" : "source"}`,
        mask,
        covered,
        mean: sum.map((v) => v / covered),
      });
      renderer.setRenderTarget(null);
      renderer.render(scene, camera);
      const image = new Image();
      image.src = renderer.domElement.toDataURL();
      image.title = results.at(-1)!.name;
      const label = document.createElement("figure");
      label.append(image, document.createTextNode(image.title));
      label.style.display = "inline-block";
      document.body.append(label);
    }
  check(
    JSON.stringify(results[0]!.mask) === JSON.stringify(results[1]!.mask),
    "Front source mode changed physical gaps",
  );
  check(
    JSON.stringify(results[2]!.mask) === JSON.stringify(results[3]!.mask),
    "Back source mode changed physical gaps",
  );
  check(
    results[0]!.mean[1]! > results[0]!.mean[0]! + 50,
    "Normal view did not retain green RGB independently of zero ownership",
  );
  for (const result of results.slice(1))
    check(
      Math.abs(result.mean[0]! - result.mean[1]!) < 3 &&
        Math.abs(result.mean[1]! - result.mean[2]!) < 3,
      `${result.name} not neutral`,
    );
  target.dispose();
  renderer.dispose();
  return {
    status: "PASS",
    views: results.map(({ mask: _mask, ...result }) => result),
    coverage: "physical alpha gaps unchanged in normal/source modes and both sides",
  };
}
run()
  .then((result) => {
    (window as any).__foliageCheck = result;
  })
  .catch((error) => {
    (window as any).__foliageCheck = { status: "FAIL", error: String(error), stack: error.stack };
  });
