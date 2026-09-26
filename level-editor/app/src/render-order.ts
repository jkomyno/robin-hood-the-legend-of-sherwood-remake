import type { RenderItem } from "three";

const compare = (a: string, b: string) => a < b ? -1 : a > b ? 1 : 0;
/** Material allocation follows asynchronous image decoding. Stable identities
 * keep coplanar surfaces consistent across reloads and asset partitioning. */
export function stableOpaqueSort(a: RenderItem, b: RenderItem) {
  return a.groupOrder - b.groupOrder || a.renderOrder - b.renderOrder ||
    compare(a.material.name, b.material.name) || a.z - b.z ||
    compare(a.object.name, b.object.name) || a.id - b.id;
}
