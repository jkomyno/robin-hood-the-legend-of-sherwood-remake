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
const directory = (prefix = "", base = staged): FileSystemDirectoryHandle =>
  ({
    async getDirectoryHandle(name: string) {
      return directory(prefix + name + "/", base);
    },
    async getFileHandle(name: string) {
      let response = await fetch(base + prefix + name);
      if (response.status === 404) response = await fetch("/library/" + prefix + name);
      if (!response.ok) throw new Error(`Missing ${prefix}${name}: ${response.status}`);
      const file = new File([await response.arrayBuffer()], name);
      return { getFile: async () => file };
    },
  }) as unknown as FileSystemDirectoryHandle;
function viewport(document: Level3D) {
  return new EditorViewport({
    document: () => document,
    selection: () => null,
    level: () => null,
    showObstacles: () => false,
    showElevation: () => false,
    onSelection: () => {},
    commitTransform: () => {},
  });
}
async function main() {
  const renderer = new THREE.WebGLRenderer({ antialias: false });
  renderer.setOpaqueSort(stableOpaqueSort);
  renderer.setSize(1024, 768);
  const target = new THREE.WebGLRenderTarget(1024, 768);
  renderer.setRenderTarget(target);
  const document = (await (
    await fetch(staged + `scenes/${name}.rhlos-map.json`)
  ).json()) as Level3D;
  const baselineDocument = query.has("baselineDocument")
    ? ((await (
        await fetch(query.get("baselineDocument")! + `scenes/${name}.rhlos-map.json`)
      ).json()) as Level3D)
    : document;
  const root = directory();
  result.textContent = "Loading baseline " + name;
  const baselineCandidate = await (async () => {
    if (query.has("baselineCatalog"))
      return prepareMapCandidate(name, directory("", query.get("baselineCatalog")!), null);
    const asset = (await new GLTFLoader().loadAsync(baseline + `scenes/${name}-volumes.scene.glb`))
      .scene;
    const map = asset.children.find((node) => node.name === "map")!;
    const ground = map.children.find((node) => node.name === "ground") ?? null;
    const sources = new Map<string, THREE.Object3D>();
    for (const group of map.children)
      if (group !== ground) for (const part of group.children) sources.set(part.name, part);
    for (const reference of baselineDocument.assetSources ?? []) {
      const external = await prepareProjectionAsset(root, reference, document.map, reference);
      asset.add(external.asset);
      for (const [key, value] of external.sources) sources.set(key, value);
    }
    return { asset, ground, sources, document: baselineDocument };
  })();
  const before = viewport(baselineCandidate.document);
  before.replaceMap(
    baselineCandidate.asset,
    baselineCandidate.ground,
    baselineCandidate.sources,
    baselineCandidate.document.assetSources,
  );
  before.syncViews(baselineCandidate.document);
  const bounds = new THREE.Box3().setFromObject(before["mapRoot"]);
  const center = bounds.getCenter(new THREE.Vector3());
  const distance = bounds.getSize(new THREE.Vector3()).length();
  const half = document.size ? document.size[1] / 2 : distance / 2;
  const cameras = [
    [
      0,
      Math.sin((document.camera.elevation_deg * Math.PI) / 180),
      Math.cos((document.camera.elevation_deg * Math.PI) / 180),
    ],
    [1, 1, 1],
  ].map((direction) => {
    const camera = new THREE.OrthographicCamera(
      (-half * 4) / 3,
      (half * 4) / 3,
      half,
      -half,
      0.1,
      distance * 5,
    );
    camera.position
      .copy(center)
      .addScaledVector(new THREE.Vector3(...direction).normalize(), distance * 2);
    camera.lookAt(center);
    camera.updateMatrixWorld();
    return camera;
  });
  const capture = (view: EditorViewport) =>
    cameras.map((camera) => {
      renderer.render(view["scene"], camera);
      const pixels = new Uint8Array(1024 * 768 * 4);
      renderer.readRenderTargetPixels(target, 0, 0, 1024, 768, pixels);
      return pixels;
    });
  const patches = before.patchPreviews().map((patch) => ({ id: patch.id, name: patch.name }));
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
    const asset = (await new GLTFLoader().loadAsync(baseline + `scenes/${name}-volumes.scene.glb`))
      .scene;
    const map = asset.children.find((node) => node.name === "map")!;
    const ground = map.children.find((node) => node.name === "ground") ?? null;
    const sources = new Map<string, THREE.Object3D>();
    for (const group of map.children)
      if (group !== ground) for (const part of group.children) sources.set(part.name, part);
    return { asset, ground, sources, document };
  })();
  const after = viewport(candidate.document);
  after.replaceMap(
    candidate.asset,
    candidate.ground,
    candidate.sources,
    candidate.document.assetSources,
  );
  after.syncViews(candidate.document);
  if (
    JSON.stringify(after.patchPreviews().map((patch) => ({ id: patch.id, name: patch.name }))) !==
    JSON.stringify(patches)
  )
    throw new Error(
      "Patch metadata differs: " +
        JSON.stringify({ before: patches, after: after.patchPreviews() }),
    );
  let compared = 0;
  const differences: unknown[] = [];
  for (let state = 0; state < expected.length; state++) {
    if (state) for (const patch of patches) after.setPatchRevealed(patch.id, true);
    const actual = capture(after);
    for (let camera = 0; camera < cameras.length; camera++) {
      const previous = expected[state]![camera]!,
        next = actual[camera]!;
      let changed = 0,
        max = 0,
        totalDelta = 0,
        changedPixels = 0;
      for (let i = 0; i < next.length; i += 4) {
        let different = false;
        for (let c = 0; c < 4; c++) {
          const delta = Math.abs(previous[i + c]! - next[i + c]!);
          totalDelta += delta;
          if (delta) {
            changed++;
            different = true;
            max = Math.max(max, delta);
          }
        }
        if (different) changedPixels++;
      }
      if (changed) {
        differences.push({
          state,
          camera,
          changed,
          changedPixels,
          max,
          meanDelta: totalDelta / next.length,
        });
        if (query.has("capture") && state === 0 && camera === 0) {
          const encode = (pixels: Uint8Array) => {
            const canvas = window.document.createElement("canvas");
            canvas.width = 1024;
            canvas.height = 768;
            const context = canvas.getContext("2d")!;
            const image = context.createImageData(1024, 768);
            for (let row = 0; row < 768; row++)
              image.data.set(pixels.subarray(row * 4096, (row + 1) * 4096), (767 - row) * 4096);
            context.putImageData(image, 0, 0);
            return canvas.toDataURL("image/png");
          };
          const diff = new Uint8Array(next.length);
          for (let i = 0; i < diff.length; i += 4) {
            diff[i] = Math.min(
              255,
              5 * Math.max(...[0, 1, 2].map((c) => Math.abs(previous[i + c]! - next[i + c]!))),
            );
            diff[i + 3] = 255;
          }
          (window as any).__migrationImages = {
            before: encode(previous),
            after: encode(next),
            difference: encode(diff),
          };
        }
        if (
          query.has("exact") ||
          changedPixels > 1024 * 768 * 0.005 ||
          totalDelta / next.length > 0.05
        )
          throw new Error(
            `${name}: state ${state}, camera ${camera}: ${changed} changed channels, max delta ${max}`,
          );
      }
      compared++;
    }
  }
  after.dispose();
  target.dispose();
  renderer.dispose();

  result.textContent = `PASS ${name}: ${compared} ${query.has("exact") ? "pixel-identical renders" : "renders within rounding tolerance"}, ${candidate.document.objects.length} parts, ${patches.length} patch previews; ${JSON.stringify(differences)}`;
}
main().catch((error) => {
  result.textContent = "FAIL " + (error.stack ?? error);
});
