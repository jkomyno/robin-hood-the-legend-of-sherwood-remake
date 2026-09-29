import * as THREE from "three";
import { gameToScene, terrainPatches, type GroundRegion, type Level3D } from "@rle/shared";

import { terrainTexture } from "./terrain-texture.ts";

export class TerrainLayer {
  readonly root = new THREE.Group();
  private readonly materials = new Map<GroundRegion["material"], THREE.MeshBasicMaterial>();
  private readonly bankMaterial = new THREE.MeshBasicMaterial({
    color: 0xb5a58d,
    map: terrainTexture("dirt"),
    side: THREE.DoubleSide,
  });
  private material(kind: GroundRegion["material"]) {
    let material = this.materials.get(kind);
    if (!material) {
      material = new THREE.MeshBasicMaterial({ map: terrainTexture(kind), side: THREE.DoubleSide });
      this.materials.set(kind, material);
    }
    return material;
  }
  private clearGeometry(root = this.root) {
    root.traverse((node) => {
      if (node instanceof THREE.Mesh) node.geometry.dispose();
    });
    root.clear();
  }
  private terrain: Level3D["terrain"];
  private splines: Level3D["splines"];
  private camera: Level3D["camera"] | undefined;
  sync(document: Level3D) {
    if (
      this.terrain === document.terrain &&
      this.splines === document.splines &&
      this.camera === document.camera
    )
      return;
    // Complete construction before replacing the last valid view.
    const next = new THREE.Group();
    try {
      const patches = terrainPatches(document, false);
      const floor = Math.min(0, ...patches.map((p) => p.height));
      for (const patch of patches) {
        const shape = new THREE.Shape(patch.polygon.map((p) => new THREE.Vector2(...p)));
        shape.holes = patch.holes.map((r) => new THREE.Path(r.map((p) => new THREE.Vector2(...p))));
        const geometry = new THREE.ShapeGeometry(shape);
        const positions = geometry.getAttribute("position"),
          uv = geometry.getAttribute("uv");
        for (let i = 0; i < positions.count; i++) {
          const x = positions.getX(i),
            y = positions.getY(i);
          positions.setXYZ(i, ...gameToScene(document.camera, x, y, patch.height));
          uv.setXY(i, x / 256, y / 256);
        }
        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(geometry, this.material(patch.material));
        mesh.userData.terrainSurface = true;
        const regionId = patch.id.slice(0, patch.id.lastIndexOf("/"));
        mesh.userData.terrainRegion = document.terrain?.find((r) => r.id === regionId)?.id;
        mesh.userData.water = patch.material === "water";
        mesh.userData.noSunShadow = true;
        next.add(mesh);
        if (patch.height > floor) {
          const vertices: number[] = [],
            bankUvs: number[] = [];
          for (const ring of [patch.polygon, ...patch.holes])
            for (let i = 0; i < ring.length; i++) {
              const a = ring[i]!,
                b = ring[(i + 1) % ring.length]!;
              const topA = gameToScene(document.camera, ...a, patch.height),
                topB = gameToScene(document.camera, ...b, patch.height);
              const lowA = gameToScene(document.camera, ...a, floor),
                lowB = gameToScene(document.camera, ...b, floor);
              vertices.push(...topA, ...lowA, ...topB, ...topB, ...lowA, ...lowB);
              const span = Math.hypot(b[0] - a[0], b[1] - a[1]) / 256;
              const top = patch.height / 256,
                bottom = floor / 256;
              bankUvs.push(0, top, 0, bottom, span, top, span, top, 0, bottom, span, bottom);
            }
          const sides = new THREE.BufferGeometry();
          sides.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
          sides.setAttribute("uv", new THREE.Float32BufferAttribute(bankUvs, 2));
          const bank = new THREE.Mesh(sides, this.bankMaterial);
          bank.userData.noSunShadow = true;
          next.add(bank);
        }
      }
    } catch (error) {
      this.clearGeometry(next);
      throw error;
    }
    this.clearGeometry();
    for (const child of next.children.slice()) this.root.add(child);
    this.terrain = document.terrain;
    this.splines = document.splines;
    this.camera = document.camera;
  }
  clear() {
    this.clearGeometry();
    for (const material of this.materials.values()) {
      material.map?.dispose();
      material.dispose();
    }
    this.materials.clear();
    this.bankMaterial.map?.dispose();
    this.bankMaterial.dispose();
    this.terrain = undefined;
    this.splines = undefined;
    this.camera = undefined;
  }
}
