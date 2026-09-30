import { render } from "@solidjs/web";
import { createSignal } from "solid-js";
import { parseStoredMap, serializeStoredMap, type Level3D } from "@rle/shared";
import * as THREE from "three";
import MissionPanel from "../src/MissionPanel.tsx";
import { EditorViewport } from "../src/editor-viewport.ts";
import { compileMap } from "../src/map-compile.ts";
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
      <div id="view" style={{ flex: "1", position: "relative" }} />
      <aside class="editor-panel" style={{ width: "340px", overflow: "auto" }}>
        <MissionPanel
          document={doc}
          commit={commit}
          viewport={viewport}
          active={active()}
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
async function mapClick(offset = 0) {
  const canvas = document.querySelector("canvas")!;
  const rect = canvas.getBoundingClientRect();
  const options = {
    clientX: rect.left + rect.width / 2 + offset,
    clientY: rect.top + rect.height / 2,
    button: 0,
    bubbles: true,
  };
  canvas.dispatchEvent(new PointerEvent("pointerdown", options));
  canvas.dispatchEvent(new PointerEvent("pointerup", options));
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
  await mapClick();
  check(current.mission?.spawnPoints.length === 1, "Map click did not create PC spawn");
  check(current.mission?.soldiers.length === 0, "PC created a soldier");
  await button("Add NPC");
  await mapClick(40);
  check(current.mission?.soldiers.length === 1, "Map click did not create NPC soldier");
  const old = current.mission!.soldiers[0]!.position[0];
  await button("Move on map");
  await mapClick(100);
  check(current.mission!.soldiers[0]!.position[0] !== old, "Move did not reposition soldier");
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
    "PASS mission placement, move, cancel, removal, undo, save/reopen, export and marker-free map bake";
}
void run().catch((error) => {
  document.querySelector("#result")!.textContent = "FAIL " + (error.stack ?? error);
});
