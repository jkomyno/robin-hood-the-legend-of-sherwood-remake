import * as THREE from "three";
import { gameToScene, type Level3D } from "@rle/shared";
import { decode } from "fast-png";
import { unzipSync } from "fflate";
import { bakeScene, renderMapBake } from "../src/map-bake-render.ts";
import { compileMap, packageCompiledMap } from "../src/map-compile.ts";
import { PatchDisplay, applyPlacementPatches } from "../src/patch-display.ts";
import {
  planAppearanceRegions,
  bakeAppearanceRegions,
  bindBakeAppearances,
} from "../src/map-appearance-bake.ts";
import { packageAppearanceRegions } from "../src/map-appearance.ts";
import { endpointAppearanceCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";

function check(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}
try {
  const document: Level3D = {
    version: 1,
    map: "Bake Contract",
    sceneAssets: [],
    size: [1100, 128],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    objects: [],
    groups: [],
  };
  const camera = document.camera;
  document.objects.push({
    id: "wall",
    node: "wall",
    kind: "building",
    source: { map: document.map, obstacle: 0 },
    transform: { dx: 0, dy: 0, dz: 0, rot_deg: 0 },
    obstacle: {
      points: [
        [0, 30],
        [40, 30],
        [40, 70],
        [0, 70],
      ].map(([x, y]) => ({ x: x!, y: y!, z_bottom: 0, z_top: 20 })),
      opaque: true,
      solid: true,
      mouse: true,
      projection_area: null,
      show_shadow_polygon: false,
      default_material: 0,
      material_indices: [],
    },
  });
  const root = new THREE.Group();
  const surface = (rect: number[], color: number, height = 0) => {
    const [x, y, w, h] = rect as [number, number, number, number];
    const geometry = new THREE.BufferGeometry().setFromPoints(
      [
        [x, y],
        [x + w, y],
        [x + w, y + h],
        [x, y + h],
      ].map(([px, py]) => new THREE.Vector3(...gameToScene(camera, px!, py!, height))),
    );
    geometry.setIndex([0, 2, 1, 0, 3, 2]);
    return new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }));
  };
  // Nonzero crop origin exercises camera rebasing and ground-depth normalization.
  root.add(surface([-20, -10, 1100, 128], 0x808080));
  const maskOwned = surface([0, 30, 40, 40], 0xff0000, 20);
  maskOwned.userData.map_bake_object_id = "mask-owned-wall";
  root.add(maskOwned);
  // This surface crosses the tile boundary at output X=1024.
  root.add(surface([990, 30, 60, 40], 0x00ff00, 20));
  const alphaTexture = new THREE.DataTexture(new Uint8Array([255, 255, 255, 0]), 1, 1);
  alphaTexture.needsUpdate = true;
  const physicalCutout = surface([80, 30, 40, 40], 0x0000ff, 20);
  physicalCutout.geometry.setAttribute(
    "uv",
    new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2),
  );
  physicalCutout.material.map = alphaTexture;
  physicalCutout.material.alphaTest = 0.5;
  root.add(physicalCutout);
  const ownership = physicalCutout.clone();
  ownership.position.x += 80;
  ownership.material = physicalCutout.material.clone();
  ownership.material.userData.source_ownership_fill = "synthesized";
  root.add(ownership);
  const hidden = surface([-20, -10, 1100, 128], 0x0000ff, 25);
  hidden.visible = false;
  root.add(hidden);
  const compiled = compileMap(document, [-20, -10, 1100, 128]);
  const rendered = renderMapBake(bakeScene([root]), camera, compiled.bounds);
  const pixel = (x: number, y: number) =>
    rendered.color.slice((y * 1100 + x) * 4, (y * 1100 + x) * 4 + 3);
  check(
    pixel(5, 5).every((value) => Math.abs(value - 128) <= 1),
    `sRGB background ${pixel(5, 5)}`,
  );
  check(pixel(30, 30).join() === "255,0,0", `crop or vertical orientation ${pixel(30, 30)}`);
  check(pixel(1023, 30).join() === "0,255,0" && pixel(1024, 30).join() === "0,255,0", "tile seam");
  const expectedDepth = Math.round(((30.5 + 20) / 128) * 65535);
  check(
    pixel(110, 30).every((value) => Math.abs(value - 128) <= 1),
    "physical alpha cutout",
  );
  check(pixel(190, 30).join() === "0,0,255", "ownership alpha must not erase opaque geometry");
  check(
    Math.abs(rendered.depth[30 * 1100 + 110]! - Math.round((30.5 / 128) * 65535)) <= 2,
    "cutout depth must reveal ground",
  );
  check(Math.abs(rendered.depth[30 * 1100 + 190]! - expectedDepth) <= 2, "ownership alpha depth");
  check(
    Math.abs(rendered.depth[30 * 1100 + 30]! - expectedDepth) <= 2,
    `depth mismatch: ${rendered.depth[30 * 1100 + 30]} expected ${expectedDepth}`,
  );
  check(
    Math.abs(rendered.depth[5 * 1100 + 5]! - Math.round((5.5 / 128) * 65535)) <= 2,
    "ground depth",
  );
  const archive = await packageCompiledMap(compiled, rendered);
  const maskControlled = renderMapBake(
    bakeScene([root]),
    camera,
    compiled.bounds,
    undefined,
    undefined,
    new Set(["mask-owned-wall"]),
  );
  check(
    maskControlled.color.every((value, index) => value === rendered.color[index]),
    "mask ownership must preserve every color pixel",
  );
  check(
    Math.abs(maskControlled.depth[30 * 1100 + 30]! - Math.round((30.5 / 128) * 65535)) <= 2,
    "mask-controlled wall must reveal underlying ground depth",
  );
  check(
    maskControlled.depth[30 * 1100 + 1024] === rendered.depth[30 * 1100 + 1024],
    "unrelated wall must retain depth occlusion",
  );
  // Reuse one snapshot across state changes, including meshes hidden on its first pass.
  const stateRoot = new THREE.Group();
  const stateGround = surface([0, 0, 1100, 128], 0x808080);
  const initialSurface = surface([990, 30, 60, 40], 0x00ff00, 20);
  const appliedSurface = surface([990, 30, 60, 40], 0xff0000, 10);
  const endpoint = endpointAppearanceCompilerFixture();
  const transitions = compileMap(endpoint.document, [0, 0, 2000, 2000], endpoint.assets).descriptor
    .asset_geometry!.movement_transitions!;
  const stateId = transitions[0]!.id;
  const available = new Set(endpoint.document.objects.map((part) => part.node));
  for (const [mesh, id] of [
    [initialSurface, "hut-a-body"],
    [appliedSurface, "hut-a-open"],
  ] as const) {
    const part = endpoint.document.objects.find((part) => part.id === id)!;
    mesh.userData.map_bake_object_id = id;
    applyPlacementPatches(mesh, endpoint.document, part, available);
  }
  appliedSurface.visible = false;
  stateRoot.add(stateGround, initialSurface, appliedSurface);
  const snapshot = bakeScene([stateRoot]);
  bindBakeAppearances(snapshot, endpoint.document, endpoint.assets, transitions);
  const parent = new THREE.Group();
  const before = new THREE.Group();
  const after = new THREE.Group();
  parent.add(before, snapshot, after);
  const originalMaterials = [
    stateGround.material,
    initialSurface.material,
    appliedSurface.material,
  ];
  let borrowedDisposals = 0;
  for (const material of originalMaterials)
    material.addEventListener("dispose", () => borrowedDisposals++);
  const verifyOwnership = () => {
    check(snapshot.parent === parent, "bake must restore its scene parent");
    check(parent.children[1] === snapshot, "bake must restore its sibling order");
    snapshot.children[0]!.children.forEach((node, index) => {
      check(
        (node as THREE.Mesh).material === originalMaterials[index],
        "bake must restore borrowed materials",
      );
    });
    check(borrowedDisposals === 0, "bake must not dispose borrowed materials");
  };
  const stateBounds: [number, number, number, number] = [0, 0, 1100, 128];
  const initialPixels = renderMapBake(snapshot, camera, stateBounds);
  verifyOwnership();
  const display = new PatchDisplay();
  display.set(stateId, true);
  display.apply(snapshot);
  const appliedPixels = renderMapBake(snapshot, camera, stateBounds);
  verifyOwnership();
  for (const x of [1023, 1024]) {
    const offset = 40 * 1100 + x;
    check(
      initialPixels.color.slice(offset * 4, offset * 4 + 3).join() === "0,255,0" &&
        appliedPixels.color.slice(offset * 4, offset * 4 + 3).join() === "255,0,0",
      "state color must change on both sides of the tile seam",
    );
    check(
      Math.abs(initialPixels.depth[offset]! - Math.round((60.5 / 128) * 65535)) <= 2 &&
        Math.abs(appliedPixels.depth[offset]! - Math.round((50.5 / 128) * 65535)) <= 2,
      "state depth must change together with its visible surface",
    );
  }
  display.clear();
  display.apply(snapshot);
  const resetPixels = renderMapBake(snapshot, camera, stateBounds);
  verifyOwnership();
  check(
    resetPixels.color.every((value, index) => value === initialPixels.color[index]) &&
      resetPixels.depth.every((value, index) => value === initialPixels.depth[index]),
    "state reset must restore every color and depth pixel",
  );
  const plans = planAppearanceRegions(snapshot, camera, stateBounds, transitions, false);
  check(
    plans.length === 1 && plans[0]!.patches.join() === stateId,
    "automatic appearance region bindings",
  );
  const regions = bakeAppearanceRegions(snapshot, plans, 1100, initialPixels, () =>
    renderMapBake(snapshot, camera, stateBounds),
  );
  const [regionX, regionY, regionWidth, regionHeight] = regions[0]!.bounds;
  check(regionWidth * regionHeight < 1100 * 128, "state images should crop unaffected map pixels");
  const stateFiles = packageAppearanceRegions(
    "state",
    1100,
    128,
    initialPixels,
    regions,
    transitions,
  );
  const stateDepth = decode(stateFiles["state.appearance-0-1.depth.png"]!).data;
  const stateColor = decode(stateFiles["state.appearance-0-1.png"]!).data;
  for (const x of [1023, 1024]) {
    const local = (40 - regionY) * regionWidth + x - regionX;
    check(
      stateDepth[local] === appliedPixels.depth[40 * 1100 + x],
      "cropped state must retain full-frame depth normalization",
    );
    check(
      stateColor.slice(local * 4, local * 4 + 3).join() === "255,0,0",
      "cropped state color at tile seam",
    );
  }
  verifyOwnership();
  // A depth-pass failure must leave the snapshot usable too.
  const failingNode = snapshot.children[0]!.children[1] as THREE.Mesh;
  const unsupported = new THREE.MeshPhongMaterial();
  failingNode.material = unsupported;
  let failed = false;
  try {
    renderMapBake(snapshot, camera, stateBounds);
  } catch (error) {
    failed = error instanceof Error && error.message.includes("Cannot compile depth");
  }
  check(failed && failingNode.material === unsupported, "failed bake must restore materials");
  failingNode.material = initialSurface.material;
  verifyOwnership();
  unsupported.dispose();
  for (const mesh of [stateGround, initialSurface, appliedSurface]) {
    mesh.geometry.dispose();
    mesh.material.dispose();
  }
  const files = unzipSync(archive);
  const depth = decode(files["Data/Levels/Day/editor-bake-contract.occlusion-depth.png"]!);
  check(
    depth.depth === 16 &&
      depth.channels === 1 &&
      depth.data[30 * 1100 + 30] === rendered.depth[30 * 1100 + 30],
    "PNG depth loss",
  );
  // Acceptance runner can retain this real GPU-produced mod for the Rust loader test.
  (window as unknown as { __bakeZip: number[] }).__bakeZip = [...archive];
  documentResult(
    "PASS map bake: crop, tile seam, hidden geometry, sRGB color, ground depth, mask-owned depth, state apply/reset, automatic appearance regions, resource restoration, ZIP/PNG roundtrip",
  );
} catch (error) {
  documentResult(`FAIL ${error instanceof Error ? error.stack : String(error)}`);
}
function documentResult(text: string) {
  window.document.querySelector("#result")!.textContent = text;
}
