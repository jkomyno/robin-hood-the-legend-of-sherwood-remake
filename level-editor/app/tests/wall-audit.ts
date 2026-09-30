import * as THREE from "three";
import { openHttpLibrary } from "../src/http-library";
import {
  listProjectionAssets,
  loadProjectionAssetPreview,
  prepareProjectionAsset,
} from "../src/projection-library";
import { disposeObjectResources } from "../src/resources";
import { wallMesh } from "../src/spline-geometry";
import type { LevelSpline } from "@rle/shared";

async function main() {
  const params = new URLSearchParams(location.search);
  const library = await openHttpLibrary(params.get("library") ?? undefined);
  const entries = await listProjectionAssets(library.handle);
  const originals = params.has("splines") ? await openHttpLibrary() : library;
  const originalEntries = await listProjectionAssets(originals.handle);
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(500, 340);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const canvas = document.createElement("canvas");
  canvas.width = 1000;
  canvas.height = params.has("splines") ? 2040 : 340;
  const context = canvas.getContext("2d")!;
  function render(asset: THREE.Object3D, row: number, label = "Source asset", focus?: THREE.Box3) {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x252b32);
    scene.add(asset, new THREE.HemisphereLight(0xffffff, 0x8c93aa, 2.5));
    const light = new THREE.DirectionalLight(0xffffff, 2);
    light.position.set(3, 8, 5);
    scene.add(light);
    const bounds = new THREE.Box3().setFromObject(asset);
    const frame = focus ?? bounds;
    const center = frame.getCenter(new THREE.Vector3());
    const radius = frame.getBoundingSphere(new THREE.Sphere()).radius;
    for (const [index, direction] of [
      new THREE.Vector3(0, Math.sin((35 * Math.PI) / 180), Math.cos((35 * Math.PI) / 180)),
      new THREE.Vector3(0.8, 0.8, 1),
    ].entries()) {
      const camera = new THREE.OrthographicCamera(
        (-radius * 1.08 * 500) / 340,
        (radius * 1.08 * 500) / 340,
        radius * 1.08,
        -radius * 1.08,
        0.01,
        radius * 10,
      );
      camera.position.copy(center).add(direction.normalize().multiplyScalar(radius * 4));
      camera.lookAt(center);
      renderer.render(scene, camera);
      context.drawImage(renderer.domElement, index * 500, row * 340);
      context.fillStyle = "#e4e8ef";
      context.font = "14px sans-serif";
      context.fillText(
        `${label} · ${index ? "Angled" : "Game camera"}`,
        index * 500 + 12,
        row * 340 + 22,
      );
    }
    return { min: bounds.min.toArray(), max: bounds.max.toArray() };
  }
  Object.assign(window, {
    async auditWallAsset(id: string, recipe?: LevelSpline & { source: string }) {
      const entry = entries.find((entry) => entry.id === id);
      if (!entry) throw new Error(`Missing ${id}`);
      if (!recipe) {
        const asset = await loadProjectionAssetPreview(library.handle, entry);
        try {
          const bounds = render(asset, 0);
          return { image: canvas.toDataURL("image/webp", 0.9), bounds };
        } finally {
          disposeObjectResources([asset]);
        }
      }
      const prepared = await prepareProjectionAsset(library.handle, entry, entry.source_map);
      const generated: THREE.Object3D[] = [];
      try {
        context.fillStyle = "#252b32";
        context.fillRect(0, 0, canvas.width, canvas.height);
        const originalEntry = originalEntries.find((entry) => entry.id === recipe.source);
        if (!originalEntry) throw new Error(`Missing original ${recipe.source}`);
        const original = await loadProjectionAssetPreview(originals.handle, {
          ...originalEntry,
          preview_model: undefined,
        });
        try {
          render(original, 0, "Original compound asset");
        } finally {
          disposeObjectResources([original]);
        }
        const bounds = render(prepared.asset, 1, "Prepared strip");
        const repeat = recipe.repeatLength;
        for (const curved of [false, true]) {
          const path: LevelSpline = {
            ...recipe,
            id,
            kind: "wall",
            cornerAsset: undefined,
            closed: false,
            points: curved
              ? [
                  [0, 0, 0],
                  [repeat, -repeat * 0.15, 0],
                  [repeat * 1.8, repeat * 0.4, 0],
                  [repeat * 2.8, repeat * 0.6, 0],
                ]
              : [
                  [0, 0, 0],
                  [repeat * 3, 0, 0],
                ],
          };
          const wall = wallMesh(
            path,
            { kind: "oblique-orthographic", elevation_deg: 35 },
            prepared.sources,
          );
          const wrapper = new THREE.Group();
          wrapper.rotation.x = -Math.PI / 2;
          wrapper.add(wall);
          generated.push(wrapper);
          render(wrapper, curved ? 3 : 2, curved ? "Curved spline" : "Three repeats");
          if (!curved) {
            const height = bounds.max[1] - bounds.min[1];
            const span = Math.min(repeat * 0.45, Math.max(60, height * 0.55));
            render(
              wrapper,
              5,
              "Repeat join at center",
              new THREE.Box3(
                new THREE.Vector3(repeat - span, height * 0.65, -recipe.width / 2),
                new THREE.Vector3(repeat + span, height, recipe.width / 2),
              ),
            );
          }
        }
        const cornerEntry = originalEntries.find((entry) => entry.id === recipe.cornerAsset);
        let corner: Awaited<ReturnType<typeof prepareProjectionAsset>> | undefined;
        try {
          if (recipe.cornerAsset) {
            if (!cornerEntry) throw new Error(`Missing corner ${recipe.cornerAsset}`);
            corner = await prepareProjectionAsset(
              originals.handle,
              cornerEntry,
              cornerEntry.source_map,
            );
          }
          const wall = wallMesh(
            {
              ...recipe,
              id,
              kind: "wall",
              closed: false,
              points: [
                [0, 0, 0],
                [repeat * 2, 0, 0],
                [repeat * 2, -repeat, 0],
              ],
            },
            { kind: "oblique-orthographic", elevation_deg: 35 },
            new Map([...prepared.sources, ...(corner?.sources ?? [])]),
          );
          const wrapper = new THREE.Group();
          wrapper.rotation.x = -Math.PI / 2;
          wrapper.add(wall);
          render(wrapper, 4, corner ? "Matching corner model" : "Continuous turn");
          wall.traverse((node) => {
            if (node instanceof THREE.Mesh) node.geometry.dispose();
          });
        } finally {
          if (corner) disposeObjectResources([corner.asset]);
        }
        let vertices = 0;
        for (const object of generated)
          object.traverse((node) => {
            if (!(node instanceof THREE.Mesh)) return;
            const p = node.geometry.getAttribute("position");
            vertices += p.count;
            for (const value of p.array)
              if (!Number.isFinite(value)) throw new Error("Non-finite wall geometry");
          });
        if (!vertices) throw new Error("Empty wall geometry");
        return {
          image: canvas.toDataURL("image/webp", 0.92),
          bounds,
          vertices,
          model_sha256: prepared.reference.model_sha256,
        };
      } finally {
        for (const object of generated)
          object.traverse((node) => {
            if (node instanceof THREE.Mesh) node.geometry.dispose();
          });
        disposeObjectResources([prepared.asset]);
      }
    },
  });
  document.querySelector("#result")!.textContent = "READY";
}
void main().catch((error) => {
  document.querySelector("#result")!.textContent = "FAIL " + String(error);
});
