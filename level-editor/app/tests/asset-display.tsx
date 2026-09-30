import * as THREE from "three";
import { createTerrainGrid, gameToScene, type Level3D } from "@rle/shared";
import { EditorViewport } from "../src/editor-viewport";
import { renderMapBake } from "../src/map-bake-render";

const errors: string[] = [];
const originalError = console.error;
console.error = (...args) => {
  errors.push(args.map(String).join(" "));
  originalError(...args);
};
window.addEventListener("error", (event) => {
  errors.push(event.message);
  document.querySelector("#result")!.textContent = `FAIL: ${event.message}`;
});
const assert = (value: unknown, message: string) => {
  if (!value) throw new Error(message);
};
const cameraModel = { kind: "oblique-orthographic" as const, elevation_deg: 35 };
const current: Level3D = {
  version: 1,
  map: "Asset display test",
  size: [420, 340],
  sceneAssets: [],
  camera: cameraModel,
  terrain: createTerrainGrid([0, 0, 420, 340], 70, 0),
  groups: [],
  objects: ["cube", "foliage"].map((id) => ({
    id,
    node: id,
    kind: "scenery" as const,
    source: { map: "Asset display test" },
    transform: { dx: 0, dy: 0, dz: 0, rot_deg: 0 },
  })),
};
const cube = new THREE.Mesh(
  new THREE.BoxGeometry(80, 80, 100),
  new THREE.MeshBasicMaterial({ color: 0xd9975b }),
);
cube.position.set(...gameToScene(cameraModel, 125, 190, 50 * Math.cos((35 * Math.PI) / 180)));
const textureCanvas = document.createElement("canvas");
textureCanvas.width = textureCanvas.height = 128;
const textureContext = textureCanvas.getContext("2d")!;
textureContext.fillStyle = "#257e48";
for (const [x, y, r] of [
  [40, 50, 28],
  [80, 50, 30],
  [60, 30, 25],
  [60, 75, 33],
]) {
  textureContext.beginPath();
  textureContext.arc(x!, y!, r!, 0, Math.PI * 2);
  textureContext.fill();
}
textureContext.fillStyle = "#86552c";
textureContext.fillRect(55, 65, 10, 61);
const foliageTexture = new THREE.CanvasTexture(textureCanvas);
foliageTexture.colorSpace = THREE.SRGBColorSpace;
const foliageMaterial = new THREE.MeshBasicMaterial({
  map: foliageTexture,
  alphaTest: 0.5,
  side: THREE.DoubleSide,
});
foliageMaterial.vertexColors = true;
Object.assign(foliageMaterial.userData, {
  foliage_physical_opacity: true,
  opacity_semantics: "physical-coverage",
  source_ownership_semantics: "separate-mask",
  source_ownership_channel: "vertex-color-r",
});
const foliage = new THREE.Mesh(new THREE.PlaneGeometry(110, 130), foliageMaterial);
foliage.geometry.setAttribute(
  "color",
  new THREE.Float32BufferAttribute(
    new Float32Array(foliage.geometry.getAttribute("position").count * 3).fill(1),
    3,
  ),
);
foliage.rotation.x = Math.PI / 2;
foliage.position.set(...gameToScene(cameraModel, 285, 185, 65 * Math.cos((35 * Math.PI) / 180)));
const source = new THREE.Group();
source.add(cube, foliage);
const viewport = new EditorViewport({
  document: () => current,
  selection: () => null,
  level: () => null,
  showObstacles: () => false,
  showElevation: () => false,
  onSelection: () => {},
  commitTransform: () => {},
  onError: (error) => errors.push(error),
});
viewport.setup(document.querySelector<HTMLDivElement>("#view")!);
viewport.replaceMap(
  source,
  null,
  new Map([
    ["cube", cube],
    ["foliage", foliage],
  ]),
);
viewport.syncViews(current);
viewport.frameContent(true);
viewport.setCardinalView("N");
const internals = viewport as unknown as { renderer: THREE.WebGLRenderer };
for (const mode of ["visible", "outline", "hidden"] as const) {
  const button = document.createElement("button");
  button.textContent = mode;
  button.onclick = () => viewport.setAssetDisplayMode(mode);
  document.querySelector("#toolbar")!.append(button);
}
for (const [label, action] of [
  ["Top", () => viewport.topView()],
  ["N", () => viewport.setCardinalView("N")],
  ["E", () => viewport.setCardinalView("E")],
  ["90°", () => viewport.rotateViewQuarterTurn()],
] as const) {
  const button = document.createElement("button");
  button.textContent = label;
  button.onclick = action;
  document.querySelector("#toolbar")!.append(button);
}
async function capture(mode: "visible" | "outline" | "hidden") {
  viewport.setAssetDisplayMode(mode);
  await new Promise((resolve) => setTimeout(resolve, 150));
  return new Promise<HTMLCanvasElement>((resolve) =>
    requestAnimationFrame(() => {
      const canvas = document.createElement("canvas");
      canvas.width = internals.renderer.domElement.width;
      canvas.height = internals.renderer.domElement.height;
      canvas.getContext("2d")!.drawImage(internals.renderer.domElement, 0, 0);
      resolve(canvas);
    }),
  );
}
function difference(a: HTMLCanvasElement, b: HTMLCanvasElement) {
  const left = a.getContext("2d")!.getImageData(0, 0, a.width, a.height).data;
  const right = b.getContext("2d")!.getImageData(0, 0, b.width, b.height).data;
  let count = 0;
  for (let i = 0; i < left.length; i += 4)
    if (
      Math.abs(left[i]! - right[i]!) +
        Math.abs(left[i + 1]! - right[i + 1]!) +
        Math.abs(left[i + 2]! - right[i + 2]!) >
      24
    )
      count++;
  return count;
}
function bakePixels() {
  const { root, bounds } = (
    viewport as unknown as {
      prepareMapBake(document: Level3D): {
        root: THREE.Group;
        bounds: [number, number, number, number];
      };
    }
  ).prepareMapBake(current);
  return renderMapBake(root, cameraModel, bounds);
}
async function run() {
  await new Promise((resolve) => setTimeout(resolve, 800));
  const visible = await capture("visible");
  const baseline = bakePixels();
  const thumbnail = viewport.captureThumbnail().toDataURL();
  const outline = await capture("outline");
  const outlinedBake = bakePixels();
  assert(viewport.captureThumbnail().toDataURL() === thumbnail, "Outline leaked into thumbnail");
  const hidden = await capture("hidden");
  const hiddenBake = bakePixels();
  assert(
    viewport.captureThumbnail().toDataURL() === thumbnail,
    "Hidden mode leaked into thumbnail",
  );
  for (const pixels of [outlinedBake, hiddenBake]) {
    assert(
      pixels.color.every((v, i) => v === baseline.color[i]),
      "Display mode leaked into baked color",
    );
    assert(
      pixels.depth.every((v, i) => v === baseline.depth[i]),
      "Display mode leaked into baked depth",
    );
  }
  const solidPixels = difference(visible, hidden),
    outlinePixels = difference(outline, hidden);
  assert(solidPixels > 1000, `Assets not visible: ${solidPixels}`);
  assert(outlinePixels > 100, `Outline not rendered: ${outlinePixels}`);
  assert(
    outlinePixels < solidPixels * 0.45,
    `Outline interior not transparent: ${outlinePixels}/${solidPixels}`,
  );
  viewport.topView();
  viewport.setCardinalView("E");
  viewport.rotateViewQuarterTurn();
  await capture("outline");
  const active = (viewport as unknown as { activeCamera(): THREE.Camera }).activeCamera();
  assert(
    active.matrixWorld.elements.every(Number.isFinite),
    "Top/cardinal controls produced invalid camera geometry",
  );
  viewport.frameContent(true);
  viewport.setCardinalView("N");
  assert(errors.length === 0, errors.join("\n"));
  (window as unknown as { __migrationImages: Record<string, string> }).__migrationImages = {
    before: visible.toDataURL(),
    after: outline.toDataURL(),
    difference: hidden.toDataURL(),
  };
  viewport.setAssetDisplayMode("outline");
  document.querySelector("#result")!.textContent =
    `PASS: visible ${solidPixels} pixels, outline ${outlinePixels}; color/depth bakes and thumbnails identical in all modes`;
}
run().catch((error) => {
  document.querySelector("#result")!.textContent =
    `FAIL: ${error.stack ?? error}\n${errors.join("\n")}`;
});
