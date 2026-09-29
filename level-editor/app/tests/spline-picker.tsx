import { createEffect, createSignal } from "solid-js";
import { render } from "@solidjs/web";
import * as THREE from "three";
import { parseLevel3D, type Level3D } from "@rle/shared";
import SplinePanel from "../src/SplinePanel";
import { EditorViewport } from "../src/editor-viewport";
import type { SplineEditMode } from "../src/spline-layer";
import { openHttpLibrary } from "../src/http-library";
import { listProjectionAssets } from "../src/projection-library";
import { builtInWallPresets } from "../src/spline-presets";
import { excludedCornerAssetIds } from "../src/spline-corners";
import "../src/styles.css";

const result = document.querySelector("#result")!;
function assert(value: unknown, message: string): asserts value {
  if (!value) throw new Error(message);
}
const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 20));
async function waitFor(check: () => boolean) {
  const deadline = performance.now() + 30000;
  while (!check()) {
    if (performance.now() > deadline) throw new Error("UI update timed out");
    await tick();
  }
}
function click(label: string, scope: ParentNode = document) {
  const button = Array.from(scope.querySelectorAll<HTMLButtonElement>("button")).find(
    (button) =>
      button.querySelector("strong")?.textContent === label || button.textContent?.trim() === label,
  );
  assert(button && !button.disabled, `Missing enabled button: ${label}`);
  button.click();
}
async function main() {
  const library = await openHttpLibrary();
  const entries = await listProjectionAssets(library.handle);
  assert(
    builtInWallPresets.every((preset) => entries.some((entry) => entry.id === preset.asset)),
    "Every shipped preset must have a model",
  );
  let viewport!: EditorViewport;
  let mode: SplineEditMode | null = null;
  const editing = (): SplineEditMode | null => mode;
  let current!: () => Level3D;
  let error = "";
  const [hasLibrary, setHasLibrary] = createSignal(true);
  const dispose = render(() => {
    const [doc, setDoc] = createSignal<Level3D>({
      version: 1,
      map: "Picker test",
      sceneAssets: [],
      objects: [],
      groups: [],
      size: [1000, 1000],
      camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    });
    current = doc;
    viewport = new EditorViewport({
      document: doc,
      selection: () => null,
      onSelection: () => {},
      level: () => null,
      showObstacles: () => false,
      showElevation: () => false,
      commitTransform: () => {},
      onError: (message) => {
        error = message;
      },
    });
    viewport.replaceMap(new THREE.Group(), null, new Map());
    const setMode = viewport.setSplineEdit.bind(viewport);
    viewport.setSplineEdit = (next) => {
      mode = next;
      setMode(next);
    };
    createEffect(doc, (next) => viewport.syncViews(next, false));
    return (
      <aside style={{ width: "360px", padding: "18px" }}>
        <SplinePanel
          document={doc}
          library={() => (hasLibrary() ? library.handle : null)}
          entries={() => entries}
          viewport={viewport}
          commit={(next) => setDoc(next)}
          onError={(message) => {
            error = message;
          }}
        />
      </aside>
    );
  }, document.querySelector("#fixture")!);
  try {
    await tick();
    document.querySelector<HTMLDetailsElement>(".spline-settings")!.open = true;
    const select = document.querySelector<HTMLSelectElement>('[aria-label="Preset source map"]')!;
    select.value = "Croisement01";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await tick();
    assert(
      document.querySelectorAll(".spline-preset-grid .asset-card").length === 3,
      "Map filter keeps its bank plus path and river",
    );
    select.value = "";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await tick();
    click("Lincoln · Wattle fence");
    await waitFor(
      () =>
        !!mode &&
        !Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(
          (b) => b.textContent?.trim() === "Change wall type",
        )?.disabled,
    );
    assert(editing()?.path.sourceStraight, "Prepared strip must retain its section shape");
    const retainedGesture = editing()!;
    retainedGesture.append([0, 0, 0]);
    retainedGesture.append([250, 0, 0]);
    await tick();
    assert(
      editing()?.path.points.length === 2,
      "Rapid appends must use the live draft, including from a retained gesture callback",
    );
    retainedGesture.append([500, 0, 0]);
    click("Finish path");
    await tick();
    assert(current().splines?.length === 1, "Finished spline must publish into the document");
    assert(
      current().splines![0]!.points.length === 3,
      "Finishing must include the last pending point",
    );
    click("Change wall type");
    await tick();
    let dialog = document.querySelector<HTMLDialogElement>("dialog[open]")!;
    assert(
      dialog && dialog.getBoundingClientRect().left > 0,
      "Picker is a modal inside the viewport",
    );
    const replacement = dialog.querySelector<HTMLButtonElement>(".asset-card")!;
    const replacementName = replacement.querySelector("strong")!.textContent;
    replacement.click();
    await waitFor(() => current().splines?.[0]?.asset !== "spline-lincoln-wattle-fence");
    const preset = builtInWallPresets.find((preset) => preset.name === replacementName)!;
    assert(
      current().splines![0]!.width === preset.width,
      "Changing wall type applies its prepared dimensions",
    );
    click("Change corner type");
    await tick();
    dialog = document.querySelector<HTMLDialogElement>("dialog[open]")!;
    assert(
      dialog.querySelectorAll(".asset-card").length >= 5,
      "Corner picker contains reviewed standalone towers",
    );
    for (const id of excludedCornerAssetIds) {
      const entry = entries.find((entry) => entry.id === id);
      if (entry)
        assert(
          !Array.from(dialog.querySelectorAll("strong")).some(
            (label) => label.textContent === entry.name,
          ),
          `Rejected corner ${id} must not appear in the picker`,
        );
    }
    dialog.querySelector<HTMLButtonElement>(".asset-card")!.click();
    await waitFor(() => !!current().splines?.[0]?.cornerAsset);
    click("Change corner type");
    await tick();
    click("Continuous join — no corner model", document.querySelector("dialog[open]")!);
    await tick();
    assert(!current().splines?.[0]?.cornerAsset, "Continuous joins remove the corner model");
    parseLevel3D(JSON.parse(JSON.stringify(current())));
    assert(!error, error);
    click("Done editing");
    await tick();
    setHasLibrary(false);
    await tick();
    click("River");
    await tick();
    assert(editing()?.path.kind === "river", "River is a gallery preset");
    click("Cancel");
    await tick();
    click("Footpath");
    await tick();
    assert(editing()?.path.kind === "road", "Footpath is a gallery preset");
    assert(!document.querySelector(".spline-list"), "Saved paths must not interrupt drawing");
    assert(
      !document.querySelector('[aria-label="Path repeat length"]'),
      "Built-in surfaces must not show an ineffective repeat control",
    );
    assert(
      !document.querySelector('[aria-label="Path elevation"]'),
      "Elevation appears once a ground height is established",
    );
    editing()!.append([10, 10, 40]);
    editing()!.append([210, 10, 80]);
    await tick();
    assert(
      editing()!.path.points.every((p) => p[2] === 40),
      "Surface path stays at its first ground height",
    );
    click("Finish path");
    await tick();
    assert(current().splines?.length === 2, "Footpath must save without a library");
    assert(
      !document.querySelector('[aria-label="Control point Z"]'),
      "Surface elevations are edited together",
    );
    click("Insert point");
    await tick();
    assert(editing()!.path.points.length === 3, "Insert adds a point");
    click("Remove point");
    await tick();
    assert(editing()!.path.points.length === 2, "Remove restores two points");
    assert(
      Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(
        (b) => b.textContent === "Remove point",
      )!.disabled,
      "Minimum path points are protected",
    );
    click("Done editing");
    await tick();
    assert(
      document.querySelectorAll(".spline-list button").length === 2,
      "Done returns to saved paths",
    );
    document.querySelector<HTMLButtonElement>(".spline-list button:last-child")!.click();
    await tick();
    assert(editing()!.path.kind === "road", "Saved path reopens for editing");
    assert(!error, error);
    result.textContent =
      "PASS preset filters, drawing, switching wall dimensions, corner gallery, continuous joins, document round-trip, river and footpath";
  } finally {
    if (!new URLSearchParams(location.search).has("preview")) {
      dispose();
      viewport.dispose();
    }
  }
}
void main().catch((error) => {
  result.textContent = "FAIL " + (error instanceof Error ? error.stack : String(error));
});
