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
  const oldPresets=localStorage.getItem("rle.wallPresets");
  localStorage.removeItem("rle.wallPresets");
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
    ...Array.from({ length: 38 }, (_, index) => ({
      id: `prop-${index}`, name: index === 0 ? "Round corner tower" : `Courtyard prop ${index}`, source_map: "York", asset_type: "Prop", tags: ["courtyard"],
    })),
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
  const host = document.querySelector("#root") as HTMLElement;
  const previousDisplay = host.style.display;
  const previousDirection = host.style.flexDirection;
  host.style.display = "flex";
  host.style.flexDirection = "column";
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
    await until(() => document.querySelectorAll(".asset-card").length === 40);
    await until(() => !document.querySelector(".asset-card:first-child .preview-status"));
    const grid = document.querySelector(".asset-grid") as HTMLElement;
    const firstCard = grid.querySelector(".asset-card") as HTMLElement;
    const preview = firstCard.querySelector(".asset-preview") as HTMLElement;
    const info = firstCard.querySelector(".asset-card-info") as HTMLElement;
    const bounds = firstCard.getBoundingClientRect();
    assert(bounds.height >= preview.getBoundingClientRect().height + info.getBoundingClientRect().height,
      "Catalog rows clipped the preview or asset details");
    assert(preview.getBoundingClientRect().height > 70, "Preview collapsed in a full catalog");
    assert(grid.scrollHeight > grid.clientHeight, "Full catalog must scroll rather than compress its rows");
    const lastCard = grid.lastElementChild as HTMLElement;
    grid.scrollTop = grid.scrollHeight;
    await new Promise(resolve => requestAnimationFrame(resolve));
    assert(lastCard.getBoundingClientRect().bottom <= grid.getBoundingClientRect().bottom + 1,
      "Last asset cannot be reached by scrolling");
    grid.scrollTop = 0;
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
    // Exercise actual viewport path handling. Synthetic pointer events cannot
    // acquire native pointer capture, so the fixture supplies that browser API.
    const drawingCanvas = document.querySelector(".editor-canvas canvas") as HTMLCanvasElement;
    drawingCanvas.setPointerCapture = () => {};
    drawingCanvas.hasPointerCapture = () => false;
    const drawPoint = async (x: number, y: number) => {
      await new Promise(resolve => requestAnimationFrame(resolve));
      const rect = drawingCanvas.getBoundingClientRect();
      const init = { bubbles: true, cancelable: true, pointerId: 1, button: 0,
        clientX: rect.left + rect.width * x, clientY: rect.top + rect.height * y };
      drawingCanvas.dispatchEvent(new PointerEvent("pointerdown", init));
      drawingCanvas.dispatchEvent(new PointerEvent("pointerup", init));
      await new Promise(resolve => requestAnimationFrame(resolve));
    };
    click("Draw river");
    await until(() => !!document.querySelector('input[aria-label="Path name"]'));
    await drawPoint(0.25, 0.45);
    await drawPoint(0.5, 0.5);
    await drawPoint(0.75, 0.65);
    click("Finish path");
    await until(() => document.querySelectorAll(".spline-list button").length === 1);
    click("Save *");
    await until(() => ![...document.querySelectorAll("button")].some(button => button.textContent?.trim() === "Save *"));
    const riverSaved = JSON.parse(await files.get("scenes/York.level3d.json")!.text());
    assert(riverSaved.splines[0].points.length === 3, "River control points were not saved");
    click("Undo");
    await until(() => document.querySelectorAll(".spline-list button").length === 0);
    click("Redo");
    await until(() => document.querySelectorAll(".spline-list button").length === 1);
    select("Wall path asset", "house");
    click("Draw wall");
    await until(() => document.querySelector('input[aria-label="Path name"]')?.getAttribute("value") === "Battlement wall" ||
      (document.querySelector('input[aria-label="Path name"]') as HTMLInputElement)?.value === "Battlement wall");
    await drawPoint(0.3, 0.7);
    await drawPoint(0.55, 0.75);
    await drawPoint(0.6, 0.45);
    select("Corner tower asset","prop-0");
    await until(()=>!(document.querySelector('select[aria-label="Corner tower asset"]') as HTMLSelectElement)?.disabled);
    await until(()=>!!document.querySelector('input[aria-label="Corner tower scale"]'));
    const flip = document.querySelector('input[aria-label="Flip battlement side"]') as HTMLInputElement;
    flip.checked = true;
    flip.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
    click("Finish path");
    await until(() => document.querySelectorAll(".spline-list button").length === 2);
    await until(()=>[...document.querySelectorAll("button")].some(b=>b.textContent==="Save as wall preset"));
    click("Save as wall preset");
    click("Draw path");
    await until(()=>(document.querySelector('input[aria-label="Path name"]') as HTMLInputElement)?.value==="Footpath");
    await drawPoint(.2,.6);await drawPoint(.35,.55);
    click("Finish path");
    await until(()=>document.querySelectorAll(".spline-list button").length===3);
    const sun = document.querySelector('input[aria-label="Cast sun shadows"]') as HTMLInputElement;
    sun.checked=true;sun.dispatchEvent(new Event("change",{bubbles:true}));
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
    click("Save *");
    await until(() => ![...document.querySelectorAll("button")].some(button => button.textContent?.trim() === "Save *"));
    assert(JSON.parse(await files.get("scenes/York.level3d.json")!.text()).splines?.find((path: {kind:string}) => path.kind === "wall")?.flipCrossSection === true,
      "Battlement-side choice was not saved");
    assert(JSON.parse(await files.get("scenes/York.level3d.json")!.text()).lighting?.enabled === true,
      "Sun settings were not saved");
    const pathsSaved=JSON.parse(await files.get("scenes/York.level3d.json")!.text());
    assert(pathsSaved.splines.some((p:{kind:string;cornerAsset?:string})=>p.kind==="wall" && p.cornerAsset==="prop-0"),"Corner tower source was not saved");
    assert(pathsSaved.splines.some((p:{kind:string})=>p.kind==="road"),"Footpath was not saved");
    click("Lincoln");
    await until(() => document.querySelector(".editor-bar button.selected")?.textContent === "Lincoln");
    select("Wall preset","Battlement wall");
    await new Promise<void>(resolve=>requestAnimationFrame(()=>resolve()));
    click("Draw wall");
    await until(()=>!!document.querySelector('input[aria-label="Corner tower scale"]'));
    assert((document.querySelector('select[aria-label="Corner tower asset"]') as HTMLSelectElement).value==="prop-0","Preset did not restore its tower across levels");
    click("Cancel");
    click("York");
    await until(() => document.querySelector(".editor-bar button.selected")?.textContent === "York");
    assert(document.querySelectorAll(".spline-list button").length === 3, "River, wall and footpath failed to reload");
    assert(errors.length === 0, errors.join("\n"));
  } catch (error) {
    throw new Error(`${error}; errors: ${errors.join("; ")}; UI: ${document.querySelector("#root")?.textContent}`);
  } finally {
    if(oldPresets===null)localStorage.removeItem("rle.wallPresets");else localStorage.setItem("rle.wallPresets",oldPresets);
    dispose();
    host.style.display = previousDisplay;
    host.style.flexDirection = previousDirection;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
}
