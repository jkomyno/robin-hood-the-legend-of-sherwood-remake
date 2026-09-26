/** Pixel parity at the import boundary, using the actual editor projection. */
import { stableOpaqueSort } from "../src/render-order.ts";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { prepareMapCandidate } from "../src/map-candidate.ts";
import { prepareProjectionAsset } from "../src/projection-library.ts";
import { EditorViewport } from "../src/editor-viewport.ts";
import type { Level3D } from "@rle/shared";

const query = new URLSearchParams(location.search);
const name = query.get("map") ?? "york";
const staged = query.get("staged") ?? "/library/";
const baseline = query.get("baseline") ?? "/library/scenes/backups/map-manifest-migration/";
const result = document.querySelector("#result")!;
const directory = (prefix = ""): FileSystemDirectoryHandle => ({
  async getDirectoryHandle(name: string) { return directory(prefix + name + "/"); },
  async getFileHandle(name: string) {
    let response = await fetch(staged + prefix + name);
    if (response.status === 404) response = await fetch("/library/" + prefix + name);
    if (!response.ok) throw new Error(`Missing ${prefix}${name}: ${response.status}`);
    const file = new File([await response.arrayBuffer()], name);
    return { getFile: async () => file };
  },
}) as unknown as FileSystemDirectoryHandle;
function viewport(document: Level3D) {
  return new EditorViewport({ document: () => document, selection: () => null, level: () => null,
    showObstacles: () => false, showElevation: () => false, onSelection: () => {}, commitTransform: () => {} });
}
async function main() {
  const renderer = new THREE.WebGLRenderer({ antialias: false });
  renderer.setOpaqueSort(stableOpaqueSort);
  renderer.setSize(1024, 768);
  const target = new THREE.WebGLRenderTarget(1024, 768);
  renderer.setRenderTarget(target);
  const document = await (await fetch(staged + `scenes/${name}.level3d.json`)).json() as Level3D;
  const root = directory();
  result.textContent = "Loading baseline " + name;
  const asset = (await new GLTFLoader().loadAsync(baseline + `scenes/${name}-volumes.scene.glb`)).scene;
  const map = asset.children.find(node => node.name === "map")!;
  const ground = map.children.find(node => node.name === "ground") ?? null;
  const sources = new Map<string, THREE.Object3D>();
  for (const group of map.children) if (group !== ground) for (const part of group.children) sources.set(part.name, part);
  for (const reference of document.assetSources ?? []) {
    const external = await prepareProjectionAsset(root, reference, document.map, reference);
    asset.add(external.asset);
    for (const [key, value] of external.sources) sources.set(key, value);
  }
  const before = viewport(document);
  before.replaceMap(asset, ground, sources, document.assetSources);
  before.syncViews(document);
  const bounds = new THREE.Box3().setFromObject(before["mapRoot"]);
  const center = bounds.getCenter(new THREE.Vector3());
  const distance = bounds.getSize(new THREE.Vector3()).length();
  const half = document.size ? document.size[1] / 2 : distance / 2;
  const cameras = [[0, Math.sin(document.camera.elevation_deg * Math.PI / 180), Math.cos(document.camera.elevation_deg * Math.PI / 180)], [1, 1, 1]]
    .map(direction => {
      const camera = new THREE.OrthographicCamera(-half * 4/3, half * 4/3, half, -half, .1, distance * 5);
      camera.position.copy(center).addScaledVector(new THREE.Vector3(...direction).normalize(), distance * 2);
      camera.lookAt(center); camera.updateMatrixWorld(); return camera;
    });
  const capture = (view: EditorViewport) => cameras.map(camera => {
    renderer.render(view["scene"], camera);
    const pixels = new Uint8Array(1024 * 768 * 4);
    renderer.readRenderTargetPixels(target, 0, 0, 1024, 768, pixels);
    return pixels;
  });
  const patches = before.patchPreviews().map(patch => ({ id: patch.id, name: patch.name }));
  const expected = [capture(before)];
  if (patches.length) {
    for (const patch of patches) before.setPatchRevealed(patch.id, true);
    expected.push(capture(before));
  }
  before.dispose();
  renderer.renderLists.dispose();
  result.textContent = "Loading manifest " + name;
  const candidate = await (async () => {
    if (!query.has("repeatBaseline")) return prepareMapCandidate(name, root, null);
    const asset = (await new GLTFLoader().loadAsync(baseline + `scenes/${name}-volumes.scene.glb`)).scene;
    const map = asset.children.find(node => node.name === "map")!;
    const ground = map.children.find(node => node.name === "ground") ?? null;
    const sources = new Map<string, THREE.Object3D>();
    for (const group of map.children) if (group !== ground) for (const part of group.children) sources.set(part.name, part);
    return { asset, ground, sources, document };
  })();
  const after = viewport(candidate.document);
  after.replaceMap(candidate.asset, candidate.ground, candidate.sources, candidate.document.assetSources);
  after.syncViews(candidate.document);
  if (JSON.stringify(after.patchPreviews().map(patch => ({ id: patch.id, name: patch.name }))) !== JSON.stringify(patches)) throw new Error("Patch metadata differs");
  let compared = 0;
  for (let state = 0; state < expected.length; state++) {
    if (state) for (const patch of patches) after.setPatchRevealed(patch.id, true);
    const actual = capture(after);
    for (let camera = 0; camera < cameras.length; camera++) {
      const previous = expected[state]![camera]!, next = actual[camera]!;
      let changed = 0, max = 0;
      for (let i = 0; i < next.length; i++) if (previous[i] !== next[i]) { changed++; max = Math.max(max, Math.abs(previous[i]! - next[i]!)); }
      if (changed) throw new Error(`${name}: state ${state}, camera ${camera}: ${changed} changed channels, max delta ${max}`);
      compared++;
    }
  }
  after.dispose(); target.dispose(); renderer.dispose();
  result.textContent = `PASS ${name}: ${compared} pixel-identical renders, ${candidate.document.objects.length} parts, ${patches.length} patch previews`;
}
main().catch(error => { result.textContent = "FAIL " + (error.stack ?? error); });
