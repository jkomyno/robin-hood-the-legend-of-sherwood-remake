import { render } from "@solidjs/web";
import { createSignal } from "solid-js";
import { parseStoredMap, serializeStoredMap, type Level3D } from "@rle/shared";
import * as THREE from "three";
import TerrainPanel from "../src/TerrainPanel";
import { EditorViewport } from "../src/editor-viewport";
import { packageCompiledMap } from "../src/map-compile";
import "../src/styles.css";

let current: Level3D = {
  version: 1,
  map: "Terrain test",
  size: null,
  camera: { kind: "oblique-orthographic", elevation_deg: 35 },
  objects: [],
  groups: [],
  sceneAssets: [],
};
const [doc, setDoc] = createSignal(current);
const result = document.querySelector("#result")!;
const assert = (v: unknown, message: string) => {
  if (!v) throw new Error(message);
};
const errors: string[] = [];
const viewport = new EditorViewport({
  document: () => current,
  selection: () => null,
  level: () => null,
  showObstacles: () => false,
  showElevation: () => false,
  onSelection: () => {},
  commitTransform: () => {},
  onError: (e) => errors.push(e),
});
let commits = 0;
function commit(next: Level3D) {
  commits++;
  current = next;
  setDoc(next);
  viewport.syncViews(next);
}
const pause = () => new Promise((resolve) => setTimeout(resolve, 80));
render(
  () => (
    <div style={{ display: "flex", height: "100vh", width: "100vw" }}>
      <div
        id="view"
        class="editor-canvas"
        style={{ flex: "1", "min-width": "0", position: "relative" }}
      />
      <aside class="editor-panel" style={{ width: "340px", overflow: "auto" }}>
        <TerrainPanel
          viewport={viewport}
          document={doc}
          commit={commit}
          onError={(e) => errors.push(e)}
        />
      </aside>
    </div>
  ),
  document.querySelector("#root")!,
);
viewport.setup(document.querySelector("#view")!);
viewport.replaceMap(new THREE.Group(), null, new Map());
async function click(text: string) {
  const button = [...document.querySelectorAll("button")].find((b) => b.textContent === text);
  assert(button, `Missing ${text}`);
  button!.click();
  await pause();
}
async function set(label: string, value: string) {
  const input = document.querySelector<HTMLInputElement | HTMLSelectElement>(
    `[aria-label="${label}"]`,
  );
  assert(input, `Missing ${label}`);
  input!.value = value;
  input!.dispatchEvent(new Event("change", { bubbles: true }));
  await pause();
}
async function run() {
  await click("Add ground region");
  await set("Terrain elevation", "70");
  assert(current.terrain?.[0]?.height === 70, "Elevation control did not commit");
  await click("Add ground region");
  await set("Terrain X", "600");
  await set("Terrain Width", "150");
  await set("Terrain material", "water");
  assert(current.terrain?.[1]?.material === "water", "Material control did not commit");
  viewport.frameContent(true);
  await pause();
  current = parseStoredMap(
    JSON.parse(JSON.stringify(serializeStoredMap(current, new Map()))),
    new Map(),
  );
  setDoc(current);
  viewport.syncViews(current);
  assert(
    current.terrain?.length === 2 && current.terrain[0]!.height === 70,
    "Saved terrain did not reopen",
  );
  const before = viewport.captureThumbnail().toDataURL();
  const { compiled, pixels, appearance } = viewport.bakeMap(current, new Map());
  assert(
    compiled.descriptor.asset_geometry!.motion_data.layers.flat().length === 2,
    "River should split the land into two areas",
  );
  const zip = await packageCompiledMap(compiled, pixels, appearance);
  assert(zip.length > 1000, "Missing baked map ZIP");
  await click("Delete region");
  assert(current.terrain?.length === 1, "Delete did not commit");
  await set("Ground region", current.terrain![0]!.id);
  await set("Terrain material", "paved");
  const paved = viewport.bakeMap(current, new Map());
  assert(
    paved.compiled.descriptor.asset_geometry!.sight_obstacles.some((o) => o.default_material === 2),
    "Paved terrain must bake as stone",
  );
  assert(errors.length === 0, errors.join("\n"));
  Object.assign(window, {
    __migrationImages: { before, after: viewport.captureThumbnail().toDataURL() },
  });
  result.textContent = `PASS terrain controls, elevation, water carving, save/reload, two navigation areas and ${zip.length} byte ZIP`;
}
Object.assign(window, {
  terrainTest: {
    state: () => ({ document: current, commits, errors }),
    point: (corner: number) => {
      const internals = viewport as unknown as {
        terrainControls: { root: THREE.Group };
        activeCamera(): THREE.Camera;
        renderer: THREE.WebGLRenderer;
        gizmo: unknown;
      };
      const handle = internals.terrainControls.root.children.find(
        (n) => n.userData.terrainCorner === corner,
      )!;
      const p = handle.getWorldPosition(new THREE.Vector3()).project(internals.activeCamera());
      const r = internals.renderer.domElement.getBoundingClientRect();
      return { x: r.left + ((p.x + 1) * r.width) / 2, y: r.top + ((1 - p.y) * r.height) / 2 };
    },
    axis: () => {
      const internals = viewport as unknown as {
        gizmo: { getHelper(): THREE.Object3D };
        activeCamera(): THREE.Camera;
        renderer: THREE.WebGLRenderer;
      };
      const points: { x: number; y: number }[] = [];
      internals.gizmo.getHelper().traverseVisible((n) => {
        if (n instanceof THREE.Mesh && n.name === "Y" && n.geometry.type === "CylinderGeometry") {
          n.geometry.computeBoundingBox();
          const p = n.geometry
            .boundingBox!.getCenter(new THREE.Vector3())
            .applyMatrix4(n.matrixWorld)
            .project(internals.activeCamera());
          const r = internals.renderer.domElement.getBoundingClientRect();
          points.push({
            x: r.left + ((p.x + 1) * r.width) / 2,
            y: r.top + ((1 - p.y) * r.height) / 2,
          });
        }
      });
      if (!points.length) throw new Error("No visible terrain gizmo elevation handle");
      return points.sort((a, b) => a.y - b.y)[0];
    },
    gizmo: () => {
      const g = (viewport as unknown as { gizmo: { object?: THREE.Object3D; showY: boolean } })
        .gizmo;
      return { attached: !!g.object, vertical: g.showY };
    },
    frame: () => viewport.frameContent(true),
  },
});
async function prepareControls() {
  await click("Add ground region");
  await set("Terrain elevation", "70");
  viewport.frameContent(true);
  await pause();
  result.textContent = "READY";
}
(new URLSearchParams(location.search).has("controls") ? prepareControls() : run()).catch(
  (error) => {
    result.textContent = "FAIL " + (error.stack ?? error);
  },
);
