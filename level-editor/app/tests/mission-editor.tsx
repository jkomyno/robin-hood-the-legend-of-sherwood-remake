import { render } from "@solidjs/web";
import { createSignal } from "solid-js";
import { parseStoredMap, serializeStoredMap, type Level3D, type ProtoLevel } from "@rle/shared";
import * as THREE from "three";
import MissionPanel from "../src/MissionPanel.tsx";
import { EditorViewport } from "../src/editor-viewport.ts";
import { compileMap } from "../src/map-compile.ts";
import { openHttpLibrary } from "../src/http-library.ts";
import { loadMissionCharacterCatalog } from "../src/mission-character-catalog.ts";
import { MissionLayer } from "../src/mission-layer.ts";
import { readMission } from "../src/mission.ts";
import { loadEditableMission } from "../src/import-mission.ts";
import { readJson, subdir } from "../src/fs.ts";
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
  terrain: [
    { id: "ground", name: "Ground", bounds: [0, 0, 1000, 1000], height: 0, material: "grass" },
  ],
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
  const button = document.querySelector<HTMLElement>(`[data-character-profile="${profile}"]`)!;
  button.scrollIntoView({ block: "nearest" });
  try {
    await waitFor(
      () => button.draggable && !!button.querySelector("img")?.complete,
      "character sprite thumbnail",
    );
  } catch (error) {
    throw new Error(
      `${String(error)}: ${button.outerHTML}; ${JSON.stringify(button.getBoundingClientRect())}`,
      { cause: error },
    );
  }
  return button;
}
async function dropCharacter(profile: string, offset = 0, cancelled = false) {
  const card = await chooseProfile(profile);
  const transfer = new DataTransfer();
  const before = commits.length;
  card.dispatchEvent(
    new DragEvent("dragstart", { dataTransfer: transfer, bubbles: true, cancelable: true }),
  );
  check(commits.length === before, "Starting palette drag created a mission element");
  const canvas = document.querySelector("canvas")!;
  const rect = canvas.getBoundingClientRect();
  const options = {
    dataTransfer: transfer,
    bubbles: true,
    cancelable: true,
    clientX: rect.left + rect.width / 2 + offset,
    clientY: rect.top + rect.height / 2,
  };
  const markers = viewport["missionMarkers"];
  const existing = markers.root.children.length;
  const saved = JSON.stringify(current);
  {
    const over = new DragEvent("dragover", options);
    canvas.dispatchEvent(over);
    check(over.defaultPrevented, "Viewport did not accept character drag");
    check(markers.root.children.length === existing + 1, "Drag has no live placement preview");
    await waitFor(
      () => markers.spritesRoot.children.length === existing + 1,
      "live drag character sprite",
    );
    const ghost = markers.root.children.at(-1)!;
    const originalPosition = ghost.position.clone();
    canvas.dispatchEvent(new DragEvent("dragover", { ...options, clientX: options.clientX + 25 }));
    check(!ghost.position.equals(originalPosition), "Preview did not follow drag position");
    check(
      JSON.stringify(current) === saved && commits.length === before,
      "Live preview changed saved mission",
    );
    canvas.dispatchEvent(new DragEvent("dragleave", options));
    check(markers.root.children.length === existing, "Leaving viewport retained preview");
    canvas.dispatchEvent(new DragEvent("dragover", options));
    check(markers.root.children.length === existing + 1, "Reentering viewport lost preview");
  }
  if (!cancelled) {
    canvas.dispatchEvent(new DragEvent("drop", options));
  }
  card.dispatchEvent(new DragEvent("dragend", options));
  await pause();
  check(
    markers.root.children.length === existing + (cancelled ? 0 : 1),
    "Drag left an extra preview character",
  );
  check(
    commits.length === before + (cancelled ? 0 : 1),
    "Drop did not create exactly one undo entry",
  );
}
async function category(kind: string) {
  const select = document.querySelector<HTMLSelectElement>('[aria-label="Character category"]')!;
  select.value = kind;
  select.dispatchEvent(new Event("change", { bubbles: true }));
  await pause();
}
async function run() {
  viewport.setup(document.querySelector("#view")!);
  const canvas = document.querySelector("canvas")!;
  // Synthetic pointer events do not enter the browser's native capture table.
  canvas.setPointerCapture = () => {};
  viewport.replaceMap(new THREE.Group(), null, new Map());
  setDoc({ ...current });
  viewport.syncViews(current);
  viewport.frameContent(true);
  await pause();
  await dropCharacter("1");
  check(current.mission?.spawnPoints.length === 1, "Map click did not create PC spawn");
  check(current.mission!.spawnPoints[0]!.direction === 8, "Default PC facing is not down");
  check(current.mission?.soldiers.length === 0, "PC created a soldier");
  check(
    current.mission!.spawnPoints[0]!.profile === 1,
    "PC sprite choice did not change canonical profile",
  );
  await category("npc");
  await dropCharacter("soldier_a00", 100);
  check(current.mission?.soldiers.length === 1, "Map click did not create NPC soldier");
  check(
    current.mission!.soldiers[0]!.name === "Blue Swordsman",
    "Soldier name was not derived from type",
  );
  const profileSelect = document.querySelector<HTMLSelectElement>(
    ".mission-settings select:not([aria-label])",
  )!;
  profileSelect.value = "soldier_a01";
  profileSelect.dispatchEvent(new Event("change", { bubbles: true }));
  await pause();
  check(
    current.mission!.soldiers[0]!.name === "Yellow Swordsman",
    "Default name did not follow changed type",
  );
  const nameInput = document.querySelector<HTMLInputElement>(
    ".mission-settings input:not([type])",
  )!;
  nameInput.value = "Gate guard";
  nameInput.dispatchEvent(new Event("change", { bubbles: true }));
  await pause();
  profileSelect.value = "soldier_a00";
  profileSelect.dispatchEvent(new Event("change", { bubbles: true }));
  await pause();
  check(current.mission!.soldiers[0]!.name === "Gate guard", "Changing type overwrote custom name");
  check(current.mission!.soldiers[0]!.direction === 8, "Default NPC facing is not down");
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
  await mapClick(0, -12);
  check(
    document
      .querySelector(`[data-mission-element="${current.mission!.spawnPoints[0]!.id}"] button`)
      ?.getAttribute("aria-pressed") === "true",
    "Clicking PC sprite did not select its placement",
  );
  await mapClick(100, -12);
  check(
    document
      .querySelector(`[data-mission-element="${current.mission!.soldiers[0]!.id}"] button`)
      ?.getAttribute("aria-pressed") === "true",
    "Clicking NPC sprite did not select its placement",
  );
  const beforeDrag = [...current.mission!.soldiers[0]!.position];
  const beforeCommits = commits.length;
  const rect = canvas.getBoundingClientRect();
  const pointer = {
    clientX: rect.left + rect.width / 2 + 100,
    clientY: rect.top + rect.height / 2 - 12,
    button: 0,
    buttons: 1,
    bubbles: true,
  };
  canvas.dispatchEvent(new PointerEvent("pointerdown", pointer));
  canvas.dispatchEvent(
    new PointerEvent("pointermove", { ...pointer, clientX: pointer.clientX + 30 }),
  );
  check(commits.length === beforeCommits, "Drag preview created undo entries");
  canvas.dispatchEvent(
    new PointerEvent("pointerup", { ...pointer, clientX: pointer.clientX + 30, buttons: 0 }),
  );
  await pause();
  check(commits.length === beforeCommits + 1, "Drag did not commit exactly once");
  check(current.mission!.soldiers[0]!.position[0] !== beforeDrag[0], "Drag did not move soldier");
  check(
    current.mission!.soldiers[0]!.position[2] === beforeDrag[2],
    "Drag changed character height",
  );
  const afterDrag = JSON.stringify(current.mission);
  canvas.dispatchEvent(
    new PointerEvent("pointerdown", { ...pointer, clientX: pointer.clientX + 30 }),
  );
  canvas.dispatchEvent(
    new PointerEvent("pointermove", { ...pointer, clientX: pointer.clientX + 60 }),
  );
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  await pause();
  check(JSON.stringify(current.mission) === afterDrag, "Cancelled drag changed mission");
  check(commits.length === beforeCommits + 1, "Cancelled drag created undo entry");
  check(
    document.querySelectorAll("[data-mission-element]").length === 2,
    "Mission list is incomplete",
  );
  const pcRow = document.querySelector<HTMLButtonElement>(
    `[data-mission-element="${current.mission!.spawnPoints[0]!.id}"] button`,
  )!;
  pcRow.click();
  await pause();
  check(pcRow.getAttribute("aria-pressed") === "true", "Mission list did not select PC");
  document
    .querySelector<HTMLButtonElement>(
      `[data-mission-element="${current.mission!.soldiers[0]!.id}"] button`,
    )!
    .click();
  await pause();
  await category("pc");
  await dropCharacter("1", 0, true);
  await mapClick(-30);
  check(
    current.mission!.spawnPoints.length === 1,
    "Cancelled palette drag or map click added a PC",
  );
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
  const markers = viewport["missionMarkers"];
  check(
    markers.root.visible && markers.spritesRoot.visible,
    "Changing tabs hid mission characters",
  );
  const visibility = document.querySelector<HTMLInputElement>(
    '.mission-settings input[type="checkbox"]',
  )!;
  setActive(true);
  await pause();
  visibility.click();
  await pause();
  check(
    !markers.root.visible && !markers.spritesRoot.visible,
    "Visibility toggle did not hide characters",
  );
  setActive(false);
  await pause();
  check(!markers.spritesRoot.visible, "Changing tabs reset hidden characters");
  setActive(true);
  await pause();
  visibility.click();
  await pause();
  setActive(false);
  await pause();
  check(markers.spritesRoot.visible, "Visible characters disappeared outside Mission tab");
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
  setActive(true);
  await pause();
  const cameraBefore = viewport["camera"]!.quaternion.clone();
  const missionBeforeOrbit = JSON.stringify(current.mission);
  canvas.dispatchEvent(new PointerEvent("pointerdown", { ...pointer, button: 2, buttons: 2 }));
  canvas.dispatchEvent(
    new PointerEvent("pointermove", {
      ...pointer,
      button: 2,
      buttons: 2,
      clientX: pointer.clientX + 60,
    }),
  );
  canvas.dispatchEvent(
    new PointerEvent("pointerup", {
      ...pointer,
      button: 2,
      buttons: 0,
      clientX: pointer.clientX + 60,
    }),
  );
  check(
    !viewport["camera"]!.quaternion.equals(cameraBefore),
    "Right drag did not rotate in Mission mode",
  );
  check(
    JSON.stringify(current.mission) === missionBeforeOrbit,
    "Camera rotation changed mission characters",
  );
  const sourceLevels = await subdir(catalog.root, ["Data", "Levels"]);
  check(sourceLevels, "Library has no mission data");
  const index = { root: catalog.root, levelsDir: sourceLevels!, maps: new Set(["Croisement01"]) };
  const sourceMission = await readMission(index, "Emb01_FoA_EC");
  const sourceLevel = await readJson<ProtoLevel>(sourceLevels!, `${sourceMission.map}.rhp.json`);
  const imported = await loadEditableMission(index, sourceMission, sourceLevel, library.handle);
  check(
    imported.soldiers.length > 0 && imported.spawnPoints.length > 0,
    "Game mission import lost characters",
  );
  commit({ ...current, mission: imported });
  await pause();
  check(
    document.querySelectorAll("[data-mission-element]").length ===
      imported.soldiers.length + imported.spawnPoints.length,
    "Imported mission characters did not enter editable list",
  );
  check(
    document.querySelector(".mission-settings")!.textContent.includes("Emb01_FoA_EC"),
    "Import source missing from Mission panel",
  );
  const importedSaved = serializeStoredMap(current, new Map());
  const importedReopened = parseStoredMap(JSON.parse(JSON.stringify(importedSaved)), new Map());
  check(
    JSON.stringify(importedReopened.mission) === JSON.stringify(imported),
    "Imported mission did not survive save/reopen",
  );
  viewport.dispose();
  document.querySelector("#result")!.textContent =
    "PASS mission palette, editing, visibility, camera rotation, export and editable game-data mission import";
}
void run().catch((error) => {
  document.querySelector("#result")!.textContent = "FAIL " + (error.stack ?? error);
});
