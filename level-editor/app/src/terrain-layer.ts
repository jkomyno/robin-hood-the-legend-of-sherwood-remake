import * as THREE from "three";
import { gameToScene, terrainPatches, noise, type GroundRegion, type Level3D } from "@rle/shared";
import { disposeObjectResources } from "./resources.ts";

function groundTexture(material: GroundRegion["material"]) {
  const size = 256,
    data = new Uint8Array(size * size * 4);
  const base =
    material === "grass" ? [78, 101, 43] : material === "water" ? [49, 87, 101] : [139, 121, 84];
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const grain = Math.sin(x * 73.1 + y * 91.7) * 8;
      const u = x / size,
        v = y / size;
      const seamless = (scale: number) => {
        const a = noise(x, y, scale) * (1 - u) + noise(x - size, y, scale) * u;
        const b = noise(x, y - size, scale) * (1 - u) + noise(x - size, y - size, scale) * u;
        return a * (1 - v) + b * v - 0.5;
      };
      const shade = seamless(75) * 22 + seamless(19) * 14 + seamless(5) * 9 + grain * 0.55;
      const i = (y * size + x) * 4;
      for (let c = 0; c < 3; c++) data[i + c] = base[c]! + shade;
      data[i + 3] = 255;
    }
  const texture = new THREE.DataTexture(data, size, size);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.magFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
  return texture;
}
export class TerrainLayer {
  readonly root = new THREE.Group();
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
          uv.setXY(i, x / 512, y / 512);
        }
        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(
          geometry,
          new THREE.MeshBasicMaterial({
            map: groundTexture(patch.material),
            side: THREE.DoubleSide,
          }),
        );
        mesh.userData.terrainSurface = true;
        mesh.userData.water = patch.material === "water";
        mesh.userData.noSunShadow = true;
        next.add(mesh);
        if (patch.height > floor) {
          const vertices: number[] = [];
          for (const ring of [patch.polygon, ...patch.holes])
            for (let i = 0; i < ring.length; i++) {
              const a = ring[i]!,
                b = ring[(i + 1) % ring.length]!;
              const topA = gameToScene(document.camera, ...a, patch.height),
                topB = gameToScene(document.camera, ...b, patch.height);
              const lowA = gameToScene(document.camera, ...a, floor),
                lowB = gameToScene(document.camera, ...b, floor);
              vertices.push(...topA, ...lowA, ...topB, ...topB, ...lowA, ...lowB);
            }
          const sides = new THREE.BufferGeometry();
          sides.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
          const bank = new THREE.Mesh(
            sides,
            new THREE.MeshBasicMaterial({ color: 0x776345, side: THREE.DoubleSide }),
          );
          bank.userData.noSunShadow = true;
          next.add(bank);
        }
      }
    } catch (error) {
      disposeObjectResources([next]);
      throw error;
    }
    this.clear();
    for (const child of next.children.slice()) this.root.add(child);
    this.terrain = document.terrain;
    this.splines = document.splines;
    this.camera = document.camera;
  }
  clear() {
    disposeObjectResources([this.root]);
    this.root.clear();
    this.terrain = undefined;
    this.splines = undefined;
    this.camera = undefined;
  }
}
