import type { Document, Node } from "@gltf-transform/core";
import type { Vec3 } from "../../shared/src/scene.ts";
import type { MaskTriangle } from "../../shared/src/compile-mask-geometry.ts";

/** Read a selected part's static opaque surfaces, including descendant mesh
 * transforms. The caller converts model-world glTF coordinates into placed game
 * coordinates. Transparent materials need texture coverage extraction first. */
export function maskRecoveryMesh(
  model: Document,
  part: string,
  place: (point: Vec3) => Vec3,
): MaskTriangle[] {
  const scene = model.getRoot().getDefaultScene();
  if (!scene) throw new Error("Mask recovery model has no selected scene");
  const matches: Node[] = [];
  scene.traverse((node) => {
    if (node.getName() === part) matches.push(node);
  });
  if (matches.length !== 1) throw new Error(`Mask recovery needs one selected part: ${part}`);
  if (model.getRoot().listAnimations().length)
    throw new Error("Mask recovery requires a static model state");
  const triangles: MaskTriangle[] = [];
  matches[0]!.traverse((node) => {
    if (node.getSkin()) throw new Error(`Mask recovery does not support skinned part ${part}`);
    const matrix = node.getWorldMatrix();
    for (const primitive of node.getMesh()?.listPrimitives() ?? []) {
      if (primitive.getMode() !== 4 || primitive.listTargets().length)
        throw new Error(`Mask recovery requires static triangles: ${part}`);
      if ((primitive.getMaterial()?.getAlphaMode() ?? "OPAQUE") !== "OPAQUE")
        throw new Error(`Mask recovery needs texture coverage for ${part}`);
      const positions = primitive.getAttribute("POSITION");
      if (!positions || positions.getElementSize() !== 3)
        throw new Error(`Mask recovery has invalid positions: ${part}`);
      const indices = primitive.getIndices();
      if (indices && indices.getElementSize() !== 1)
        throw new Error(`Mask recovery has invalid indices: ${part}`);
      const count = indices?.getCount() ?? positions.getCount();
      if (count % 3) throw new Error(`Mask recovery has incomplete triangles: ${part}`);
      const cache = new Map<number, Vec3>();
      const point = (offset: number): Vec3 => {
        const index = indices?.getScalar(offset) ?? offset;
        if (!Number.isInteger(index) || index < 0 || index >= positions.getCount())
          throw new Error(`Mask recovery index outside positions: ${part}`);
        const cached = cache.get(index);
        if (cached) return cached;
        const [x, y, z] = positions.getElement(index, [0, 0, 0]);
        const world: Vec3 = [
          matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
          matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
          matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14],
        ];
        if (!world.every(Number.isFinite)) throw new Error(`Invalid mesh point: ${part}`);
        const placed = place(world);
        if (placed.length !== 3 || !placed.every(Number.isFinite))
          throw new Error(`Invalid placed mesh point: ${part}`);
        cache.set(index, placed);
        return placed;
      };
      for (let offset = 0; offset < count; offset += 3)
        triangles.push([point(offset), point(offset + 1), point(offset + 2)]);
    }
  });
  if (!triangles.length) throw new Error(`Mask recovery part has no surfaces: ${part}`);
  return triangles;
}
