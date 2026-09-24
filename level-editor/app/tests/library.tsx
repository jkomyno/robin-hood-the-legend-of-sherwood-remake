import { render } from "@solidjs/web";
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import Editor3D from "../src/Editor3D";
import { ASSET_DRAG_TYPE } from "../src/asset-library";
import { disposeObjectResources } from "../src/resources";

const assert = (value: unknown, message: string) => { if (!value) throw new Error(message); };
async function until(test: () => boolean) {
  for (let i = 0; i < 150; i++) {
    if (test()) return;
    await new Promise(resolve => setTimeout(resolve, 40));
  }
  throw new Error("Shared library acceptance timed out");
}

export async function checkSharedLibrary() {
  const files = new Map<string, File>();
  const json = (name: string, value: unknown) => files.set(name, new File([JSON.stringify(value)], name));
  const obstacle = { points: [{ x: 0, y: 0, z_bottom: 0, z_top: 30 }, { x: 30, y: 0, z_bottom: 0, z_top: 30 },
    { x: 0, y: 30, z_bottom: 0, z_top: 30 }], solid: true, opaque: true, mouse: true,
    show_shadow_polygon: false, default_material: 0, material_indices: [], projection_area: null };
  const camera = { kind: "oblique-orthographic", elevation_deg: 35 };
  async function model(id?: string) {
    const root = new THREE.Group();
    root.name = "map";
    root.rotation.x = -Math.PI / 2;
    const group = new THREE.Group();
    group.name = "buildings";
    if (id) group.userData.asset_group = id;
    root.add(group);
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(30, 30, 30), new THREE.MeshBasicMaterial({ color: 0x46bbaa }));
    mesh.position.z = 15;
    mesh.name = "building-000";
    mesh.userData.source_obstacle = 0;
    group.add(mesh);
    const bytes = await new GLTFExporter().parseAsync(root, { binary: true }) as ArrayBuffer;
    disposeObjectResources([root]);
    return new File([bytes], "model.glb");
  }
  for (const name of ["York", "Lincoln"]) {
    files.set(`scenes/${name}-volumes.scene.glb`, await model());
    json(`scenes/${name}-volumes.scene.json`, { version: 1, map: name, size: [400, 400], camera, placements: [] });
    json(`scenes/${name}.level3d.json`, { version: 1, map: name, size: [400, 400], camera,
      glb: `${name}-volumes.scene.glb`, groups: [], objects: [{
        id: "building-000", node: "building-000", kind: "building", source: { map: name, obstacle: 0 },
        obstacle, transform: { dx: 0, dy: 0, dz: 0, rot_deg: 0 },
      }] });
  }
  const entries = [
    { id: "house", name: "Stone House", source_map: "Leicester", asset_type: "Building", tags: ["stone"] },
    { id: "tree", name: "Oak Tree", source_map: "Derby", asset_type: "Vegetation", tags: ["oak"] },
  ].map(entry => ({ ...entry, descriptor: `${entry.id}/asset.json`, model: `${entry.id}/model.glb` }));
  json("3d-assets/index.json", { version: 1, assets: entries });
  for (const entry of entries) {
    files.set(`3d-assets/${entry.model}`, await model(entry.id));
    json(`3d-assets/${entry.descriptor}`, { version: 1, kind: "projection-mapped-asset", ...entry, model: "model.glb",
      source_origin_scene: [0, 0, 0], source_origin_game: [0, 0, 0],
      parts: [{ node: "building-000", name: entry.name, source_obstacle: 0, obstacle_local_game: obstacle }] });
  }
  const handle = (prefix: string): FileSystemDirectoryHandle => ({
    name: "shared-library-fixture", kind: "directory",
    async getDirectoryHandle(name: string) {
      const next = prefix + name + "/";
      if (![...files.keys()].some(path => path.startsWith(next))) throw new DOMException(name, "NotFoundError");
      return handle(next);
    },
    async getFileHandle(name: string) {
      const path = prefix + name;
      if (!files.has(path)) throw new DOMException(path, "NotFoundError");
      return {
        getFile: async () => files.get(path)!,
        createWritable: async () => {
          let value = "";
          return { write: async (text: string) => { value = text; },
            close: async () => { files.set(path, new File([value], name)); }, abort: async () => {} };
        },
      };
    },
    async *entries() {
      for (const path of files.keys()) if (path.startsWith(prefix) && !path.slice(prefix.length).includes("/"))
        yield [path.slice(prefix.length), { kind: "file" }];
    },
  }) as unknown as FileSystemDirectoryHandle;
  const library = { handle: handle("") };
  const errors: string[] = [];
  const dispose = render(() => <Editor3D index={() => null} library={() => library}
    onError={error => errors.push(error)} onStatus={() => {}} />, document.querySelector("#root")!);
  const click = (label: string) => {
    const button = [...document.querySelectorAll("button")].find(button => button.textContent?.trim() === label);
    assert(button && !button.disabled, `Missing enabled button: ${label}`);
    button!.click();
  };
  const select = (label: string, value: string) => {
    const element = document.querySelector(`select[aria-label="${label}"]`) as HTMLSelectElement;
    element.value = value;
    element.dispatchEvent(new Event("change", { bubbles: true }));
  };
  try {
    await until(() => document.querySelectorAll(".asset-card").length === 2);
    await until(() => document.querySelectorAll(".preview-status").length === 0);
    const canvas = document.querySelector(".asset-preview canvas") as HTMLCanvasElement;
    const pixels = canvas.getContext("2d")!.getImageData(0, 0, canvas.width, canvas.height).data;
    assert(pixels.some((value, index) => index % 4 === 3 && value > 0), "3D preview did not render any geometry");
    select("Asset type", "Building");
    await until(() => document.querySelectorAll(".asset-card").length === 1);
    select("Source level", "Derby");
    await until(() => document.querySelectorAll(".asset-card").length === 0);
    select("Source level", "Leicester");
    await until(() => document.querySelectorAll(".asset-card").length === 1);
    click("York");
    await until(() => document.querySelector(".editor-bar button.selected")?.textContent === "York");
    const card = document.querySelector(".asset-card")!;
    const transfer = new DataTransfer();
    card.dispatchEvent(new DragEvent("dragstart", { bubbles: true, dataTransfer: transfer }));
    assert(transfer.getData(ASSET_DRAG_TYPE) === "house", "Drag did not identify the asset");
    const viewport = document.querySelector(".editor-canvas")!;
    const rect = viewport.getBoundingClientRect();
    viewport.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: transfer,
      clientX: rect.left + rect.width * 0.6, clientY: rect.top + rect.height * 0.6 }));
    await until(() => document.querySelector(".editor-status")?.textContent === "Added Stone House");
    click("Save *");
    await until(() => ![...document.querySelectorAll("button")].some(button => button.textContent?.trim() === "Save *"));
    const saved = JSON.parse(await files.get("scenes/York.level3d.json")!.text());
    assert(saved.objects.some((part: { source: { map: string } }) => part.source.map === "Leicester"), "Cross-level source was lost");
    assert(saved.groups[0].transform.dx !== 200, "Drop used map center instead of cursor");
    click("Undo");
    await until(() => document.querySelectorAll(".object-list li").length === 1);
    click("Redo");
    await until(() => document.querySelectorAll(".object-list li").length > 1);
    click("Lincoln");
    await until(() => document.querySelector(".editor-bar button.selected")?.textContent === "Lincoln");
    click("York");
    await until(() => document.querySelector(".editor-bar button.selected")?.textContent === "York");
    assert(document.querySelectorAll(".object-list li").length > 1, "Saved cross-level asset failed to reload");
    assert(errors.length === 0, errors.join("\n"));
  } catch (error) {
    throw new Error(`${error}; errors: ${errors.join("; ")}; UI: ${document.querySelector("#root")?.textContent}`);
  } finally {
    dispose();
    await new Promise(resolve => setTimeout(resolve, 100));
  }
}
