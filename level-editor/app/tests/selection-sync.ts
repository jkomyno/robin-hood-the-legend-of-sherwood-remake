import { createEffect, createSignal } from "solid-js";
import { render } from "@solidjs/web";
import * as THREE from "three";
import { EditorViewport } from "../src/editor-viewport";
import type { Selection } from "../src/document-commands";
import type { Level3D } from "@rle/shared";

const result = document.querySelector("#result")!;
function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}
async function main() {
  let viewport!: EditorViewport;
  let setSelection!: (selection: Selection) => void;
  const dispose = render(() => {
    const [selection, updateSelection] = createSignal<Selection>(null);
    setSelection = updateSelection;
    viewport = new EditorViewport({
      document: () => ({ objects: [{ id: "a" }, { id: "b" }], groups: [] }) as unknown as Level3D,
      selection,
      onSelection: updateSelection,
      level: () => null,
      showObstacles: () => false,
      showElevation: () => false,
      commitTransform: () => {},
    });
    createEffect(selection, (value) => viewport.syncSelection(value));
    return null;
  }, document.createElement("div"));
  const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));
  // Inspect rendered state without allocating WebGL or a render loop.
  const state = viewport as unknown as {
    objectsRoot: THREE.Group;
    partViews: Map<string, { wrapper: THREE.Group; rot: THREE.Group; meshes: THREE.Mesh[] }>;
    gizmoFrame: THREE.Object3D;
    selectionBox: THREE.Box3Helper;
    gizmo: { attach(object: THREE.Object3D): void; detach(): void };
  };
  let attached: THREE.Object3D | null = null;
  state.gizmo = {
    attach: (object) => {
      attached = object;
    },
    detach: () => {
      attached = null;
    },
  };
  for (const [id, x] of [
    ["a", 100],
    ["b", 500],
  ] as const) {
    const wrapper = new THREE.Group();
    wrapper.position.set(x, 20, 30);
    const rot = new THREE.Group();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(10, 20, 30), new THREE.MeshBasicMaterial());
    mesh.position.set(40, 50, 60); // Geometry center deliberately differs from transform origin.
    rot.add(mesh);
    wrapper.add(rot);
    state.objectsRoot.add(wrapper);
    state.partViews.set(id, { wrapper, rot, meshes: [mesh] });
  }
  for (const id of ["a", "b", "a"]) {
    if (id === "b") setSelection({ kind: "part", id }); // Changes outside viewport picking.
    else viewport.select({ kind: "part", id });
    await flush();
    const view = state.partViews.get(id)!;
    const origin = view.wrapper.getWorldPosition(new THREE.Vector3());
    const bounds = new THREE.Box3().setFromObject(view.wrapper, true);
    assert(attached === state.gizmoFrame, "Gizmo must be attached");
    assert(
      state.gizmoFrame.position.distanceTo(origin) < 1e-9,
      "Gizmo must use the new transform origin",
    );
    assert(
      state.selectionBox.visible && state.selectionBox.box.equals(bounds),
      "Box must use the new selection immediately",
    );
    for (const [otherId, other] of state.partViews) {
      const color = (other.meshes[0]!.material as THREE.MeshBasicMaterial).color.getHex();
      assert(
        color === (otherId === id ? 0xffd27a : 0xffffff),
        "Highlight must match the box and gizmo",
      );
    }
  }
  setSelection(null);
  await flush();
  assert(
    attached === null && !state.selectionBox.visible,
    "Deselect must clear gizmo and box immediately",
  );
  dispose();
  viewport.dispose();
  result.textContent =
    "PASS reactive selection keeps highlight, bounds and transform origin synchronized";
}
void main().catch((error) => {
  result.textContent = "FAIL " + String(error);
});
