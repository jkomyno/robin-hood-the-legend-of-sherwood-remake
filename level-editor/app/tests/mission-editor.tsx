import { render } from "@solidjs/web";
import { createSignal } from "solid-js";
import { parseStoredMap, serializeStoredMap, createTerrainGrid, type Level3D } from "@rle/shared";
import * as THREE from "three";
import MissionPanel from "../src/MissionPanel.tsx";
import { EditorViewport } from "../src/editor-viewport.ts";
import { compileMap } from "../src/map-compile.ts";
import { openHttpLibrary } from "../src/http-library.ts";
import { loadMissionCharacterCatalog } from "../src/mission-character-catalog.ts";
import { MissionLayer } from "../src/mission-layer.ts";
import "../src/styles.css";

let current: Level3D = {
  version: 1,
  map: "Mission test",
  size: [1000, 1000],
  exportBounds: [-1, -1, 1003, 1003],
  camera: { kind: "oblique-orthographic", elevation_deg: 35 },
  objects: [],
  groups: [],
  sceneAssets: [],
  terrain: createTerrainGrid([0, 0, 1000, 1000], 250),
};
const [doc, setDoc] = createSignal(current);
const [active, setActive] = createSignal(true);
const library = await openHttpLibrary("/library/");
const errors: string[] = [];
const commits: Level3D[] = [];
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
function commit(next: Level3D) {
  commits.push(current);
  current = next;
  setDoc(next);
  viewport.syncViews(next);
}
render(
  () => (
    <div style={{ display: "flex", height: "100vh" }}>
      <div id="view" style={{ flex: "1", "min-width": "0", position: "relative" }} />
      <aside class="editor-panel" style={{ width: "340px", flex: "none", overflow: "auto" }}>
        <MissionPanel
          document={doc}
          commit={commit}
          viewport={viewport}
          active={active()}
          library={() => library.handle}
          onError={(error) => errors.push(error)}
        />
      </aside>
    </div>
  ),
  document.querySelector("#root")!,
);
const pause = () => new Promise((resolve) => setTimeout(resolve, 80));
const check = (condition: unknown, message: string) => {
  if (!condition) throw new Error(message);
};
async function button(text: string) {
  const node = [...document.querySelectorAll("button")].find((node) => node.textContent === text);
  check(node, `Missing button ${text}`);
  node!.click();
  await pause();
}
async function mapClick(offset = 0, verticalOffset = 0) {
  const canvas = document.querySelector("canvas")!;
  const rect = canvas.getBoundingClientRect();
  const options = {
    clientX: rect.left + rect.width / 2 + offset,
    clientY: rect.top + rect.height / 2 + verticalOffset,
    button: 0,
    bubbles: true,
  };
  canvas.dispatchEvent(new PointerEvent("pointerdown", options));
  canvas.dispatchEvent(new PointerEvent("pointerup", options));
  await pause();
}
async function waitFor(check: () => boolean, label: string) {
  const end = performance.now() + 30000;
  while (!check()) {
    if (performance.now() > end) throw new Error(`Timed out: ${label}`);
    await pause();
  }
}
async function chooseProfile(profile: string) {
  await waitFor(
    () => !!document.querySelector(`[data-character-profile="${profile}"]`),
    "character catalog",
  );
  const button = document.querySelector<HTMLButtonElement>(
    `[data-character-profile="${profile}"]`,
  )!;
  button.scrollIntoView({ block: "nearest" });
  try {
    await waitFor(
      () => !button.disabled && !!button.querySelector("img")?.complete,
      "character sprite thumbnail",
    );
  } catch (error) {
    throw new Error(
      `${String(error)}: ${button.outerHTML}; ${JSON.stringify(button.getBoundingClientRect())}`,
      { cause: error },
    );
  }
  button.click();
  await pause();
}
async function run() {
  viewport.setup(document.querySelector("#view")!);
  viewport.replaceMap(new THREE.Group(), null, new Map());
  setDoc({ ...current });
  viewport.syncViews(current);
  viewport.frameContent(true);
  await pause();
  await button("Add PC");
  await chooseProfile("1");
  check(!current.mission?.spawnPoints.length, "Choosing a PC created a placement before map click");
  await mapClick();
  check(current.mission?.spawnPoints.length === 1, "Map click did not create PC spawn");
  check(current.mission?.soldiers.length === 0, "PC created a soldier");
  check(
    current.mission!.spawnPoints[0]!.profile === 1,
    "PC sprite choice did not change canonical profile",
  );
  await button("Add NPC");
  await chooseProfile("soldier_a00");
  await mapClick(40);
  check(current.mission?.soldiers.length === 1, "Map click did not create NPC soldier");
  check(
    current.mission!.soldiers[0]!.profile === "soldier_a00",
    "NPC sprite choice did not change canonical profile",
  );
  const direction = document.querySelector<HTMLInputElement>('[aria-label="Direction (0–15)"]')!;
  check(direction.closest(".scrub-number"), "Direction does not use the numeric slider");
  direction.value = "4";
  direction.dispatchEvent(new Event("change", { bubbles: true }));
  await pause();
  check(current.mission!.soldiers[0]!.direction === 4, "Numeric slider did not change facing");
  check(
    [...document.querySelectorAll('input[type="number"]')].every((input) =>
      input.closest(".scrub-number"),
    ),
    "Raw numeric input remains in Mission controls",
  );
  const old = current.mission!.soldiers[0]!.position[0];
  await button("Move on map");
  await mapClick(100);
  check(current.mission!.soldiers[0]!.position[0] !== old, "Move did not reposition soldier");
  await mapClick(0, -12);
  check(
    document.querySelector<HTMLSelectElement>(".mission-settings select")?.value ===
      current.mission!.spawnPoints[0]!.id,
    "Clicking PC sprite did not select its placement",
  );
  await mapClick(100, -12);
  check(
    document.querySelector<HTMLSelectElement>(".mission-settings select")?.value ===
      current.mission!.soldiers[0]!.id,
    "Clicking NPC sprite did not select its placement",
  );
  await button("Add PC");
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  await pause();
  await mapClick(-30);
  check(current.mission!.spawnPoints.length === 1, "Escape did not cancel placement");
  const saved = serializeStoredMap(current, new Map());
  const reopened = parseStoredMap(JSON.parse(JSON.stringify(saved)), new Map());
  check(
    JSON.stringify(reopened.mission) === JSON.stringify(current.mission),
    "Mission did not survive save/reopen",
  );
  const compiled = compileMap(reopened, [-1, -1, 1003, 1003]);
  check(compiled.descriptor.spawn_points?.length === 1, "PC was not exported as a spawn point");
  check(compiled.descriptor.soldiers?.length === 1, "NPC was not exported as a soldier");
  await button("Delete placement");
  check(current.mission!.soldiers.length === 0, "Delete did not remove soldier");
  current = commits.pop()!;
  setDoc(current);
  viewport.syncViews(current);
  check(current.mission!.soldiers.length === 1, "Undo snapshot lost soldier");
  const catalog = await loadMissionCharacterCatalog(library.handle);
  const sprites = new MissionLayer();
  let loading = false,
    warnings: string[] = [];
  sprites.setLibrary(catalog.root, catalog.profiles, (pending, messages) => {
    loading = pending;
    warnings = messages;
  });
  sprites.sync(current);
  await waitFor(() => !loading, "viewport character sprite frames");
  check(warnings.length === 0, warnings.join("\n"));
  check(sprites.spritesRoot.children.length === 2, "PC and NPC sprites were not loaded");
  const camera = new THREE.OrthographicCamera();
  camera.position.set(500, 500, 1000);
  camera.lookAt(500, 0, 500);
  camera.updateMatrixWorld();
  sprites.update(camera, true);
  const actor = sprites.spritesRoot.children.find(
    (root) => root.userData.missionId === current.mission!.soldiers[0]!.id,
  )!.children[0] as THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>;
  check(actor.material.map?.image instanceof OffscreenCanvas, "NPC has no decoded sprite image");
  const before = actor.geometry;
  const turned = structuredClone(current);
  turned.mission!.soldiers[0]!.direction = 8;
  sprites.sync(turned);
  sprites.update(camera, true);
  check(actor.geometry !== before, "NPC facing change did not select another directional sprite");
  sprites.clear();
  check(sprites.spritesRoot.children.length === 0, "Sprite disposal retained scene objects");
  const withMarkers = viewport.bakeMap(current).pixels;
  setActive(false);
  await pause();
  const withoutMarkers = viewport.bakeMap(current).pixels;
  check(
    withMarkers.color.every((value, index) => value === withoutMarkers.color[index]),
    "Mission markers leaked into baked color",
  );
  check(
    withMarkers.depth.every((value, index) => value === withoutMarkers.depth[index]),
    "Mission markers leaked into baked depth",
  );
  check(errors.length === 0, errors.join("\n"));
  viewport.dispose();
  document.querySelector("#result")!.textContent =
    "PASS mission sprite chooser, PC/NPC sprites, facing slider, placement, save/reopen, export and sprite-free map bake";
}
void run().catch((error) => {
  document.querySelector("#result")!.textContent = "FAIL " + (error.stack ?? error);
});
