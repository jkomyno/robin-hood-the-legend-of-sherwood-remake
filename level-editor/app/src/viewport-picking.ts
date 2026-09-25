import * as THREE from "three";
import { isEffectivelyVisible } from "./patch-display.ts";

/** Start orthographic picking at the visible near plane, including signed ranges. */
export function setViewportRay(raycaster: THREE.Raycaster, ndc: THREE.Vector2, camera: THREE.Camera) {
  camera.updateMatrixWorld(true);
  raycaster.setFromCamera(ndc, camera);
  if (camera instanceof THREE.OrthographicCamera) {
    // Recover camera-space X/Y independently of the depth encoding. The
    // renderer can reverse clip-space depth, including with a signed near plane.
    raycaster.ray.origin.set(ndc.x, ndc.y, 0).applyMatrix4(camera.projectionMatrixInverse);
    raycaster.ray.origin.z = -camera.near;
    raycaster.ray.origin.applyMatrix4(camera.matrixWorld);
    raycaster.near = 0;
    raycaster.far = camera.far - camera.near;
  } else if (camera instanceof THREE.PerspectiveCamera) {
    const depth = raycaster.ray.direction.dot(camera.getWorldDirection(new THREE.Vector3()));
    raycaster.near = camera.near / depth;
    raycaster.far = camera.far / depth;
  }
}

type Pixels = { version: number; width: number; height: number; data: Uint8Array | Uint8ClampedArray; channels: number };
const cachedPixels = new WeakMap<THREE.Texture["source"], Pixels | null>();
function pixels(texture: THREE.Texture): Pixels | null {
  const cached = cachedPixels.get(texture.source);
  if (cached === null || cached?.version === texture.source.version) return cached ?? null;
  const source = texture.image as { data?: unknown; width: number; height: number; naturalWidth?: number; naturalHeight?: number } | undefined;
  if (!source) return null;
  let result: Pixels;
  if (source.data instanceof Uint8Array || source.data instanceof Uint8ClampedArray) {
    result = { version: texture.source.version, width: source.width, height: source.height,
      data: source.data, channels: source.data.length / (source.width * source.height) };
  } else {
    try {
      const width = source.naturalWidth ?? source.width, height = source.naturalHeight ?? source.height;
      const canvas = document.createElement("canvas");
      canvas.width = width; canvas.height = height;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) throw new Error("Cannot read picking texture");
      context.drawImage(source as CanvasImageSource, 0, 0);
      result = { version: texture.source.version, width, height,
        data: context.getImageData(0, 0, width, height).data, channels: 4 };
    } catch (error) {
      console.warn("Texture alpha unavailable for picking; using geometry", error);
      cachedPixels.set(texture.source, null);
      return null;
    }
  }
  cachedPixels.set(texture.source, result);
  return result;
}
function channel(texture: THREE.Texture, hit: THREE.Intersection, component: number): number {
  const uv = texture.channel === 1 ? hit.uv1 : hit.uv;
  if (!uv) return 1;
  const image = pixels(texture);
  if (!image || component >= image.channels) return 1;
  if (texture.matrixAutoUpdate) texture.updateMatrix();
  const point = texture.transformUv(uv.clone());
  const x = Math.min(image.width - 1, Math.max(0, Math.floor(point.x * image.width)));
  const y = Math.min(image.height - 1, Math.max(0, Math.floor(point.y * image.height)));
  return image.data[(y * image.width + x) * image.channels + component]! / 255;
}

/** Ray/triangle hits also include transparent atlas margins and holes in foliage. */
export function visibleSurface(hit: THREE.Intersection): boolean {
  if (!isEffectivelyVisible(hit.object)) return false;
  const mesh = hit.object as THREE.Mesh;
  if (!mesh.isMesh) return true;
  const material = (Array.isArray(mesh.material)
    ? mesh.material[hit.face?.materialIndex ?? 0] : mesh.material) as THREE.MeshBasicMaterial | undefined;
  if (!material || !material.visible) return false;
  if (!material.transparent && material.alphaTest <= 0) return true;
  let alpha = material.opacity;
  // Synthesized building atlases use alpha as provenance; the display shader
  // renders those surfaces opaque. Foliage retains physical texture coverage.
  const physicalAlpha = material.userData.source_ownership_fill !== "synthesized"
    || material.userData.foliage_physical_opacity === true;
  if (material.map && physicalAlpha) alpha *= channel(material.map, hit, 3);
  if (material.alphaMap) alpha *= channel(material.alphaMap, hit, 1);
  return alpha >= material.alphaTest && (!material.transparent || alpha > 0.01);
}
