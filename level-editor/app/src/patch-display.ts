import * as THREE from "three";
import { endpointPatchRule, patchBindingExtras, remapPatchExtras, type Level3D } from "@rle/shared";

export function isEffectivelyVisible(object: THREE.Object3D) {
  for (let node: THREE.Object3D | null = object; node; node = node.parent)
    if (!node.visible) return false;
  return true;
}

/** Patch appearance previews use reviewed graphics/covers, independently of sight geometry. */
export class PatchDisplay {
  private readonly revealed = new Set<string>();
  set(patch: string, revealed: boolean) {
    if (!patch) throw new Error("Patch ID is required");
    if (revealed) this.revealed.add(patch);
    else this.revealed.delete(patch);
  }
  clear() {
    this.revealed.clear();
  }
  isRevealed(patch: string) {
    return this.revealed.has(patch);
  }
  apply(root: THREE.Object3D) {
    root.traverse((object) => {
      const {
        reveal_material_patch: patch,
        reveal_material_state: state,
        reveal_hide_when_applied: hide,
        reveal_show_when_applied: show,
      } = object.userData;
      let visible = true;
      let controlled = false;
      if (patch !== undefined || state !== undefined) {
        if (typeof patch !== "string" || !patch || (state !== "covered" && state !== "revealed"))
          throw new Error("Invalid exported patch material state");
        visible = (state === "revealed") === this.revealed.has(patch);
        controlled = true;
      }
      if (hide !== undefined) {
        if (!Array.isArray(hide) || hide.some((id) => typeof id !== "string" || !id))
          throw new Error("Invalid reviewed patch cover IDs");
        visible &&= !hide.some((id) => this.revealed.has(id));
        controlled = true;
      }
      if (show !== undefined) {
        if (
          !Array.isArray(show) ||
          !show.length ||
          show.some((id) => typeof id !== "string" || !id)
        )
          throw new Error("Invalid reviewed patch receiver IDs");
        visible &&= show.some((id) => this.revealed.has(id));
        controlled = true;
      }
      if (controlled) object.visible = visible;
    });
  }
}

/**
 * Bind one placed part's asset-local appearance IDs to mission patch IDs, exactly as the
 * editor viewport does: the placement's (or its group's) `patches` mapping for the part's
 * asset renames every reveal trigger below `node`, and grouped endpoint variants gain their
 * hide/show rule. `node` must be this placement's own copy of the source node.
 */
export function applyPlacementPatches(
  node: THREE.Object3D,
  document: Pick<Level3D, "groups">,
  part: { node: string; group?: string; patches?: Level3D["objects"][number]["patches"] },
  availableNodes: ReadonlySet<string>,
) {
  const asset = part.node.split(":")[1]!;
  const group = part.group ? document.groups.find((item) => item.id === part.group) : undefined;
  const patches = part.group ? group?.patches?.[asset] : part.patches?.[asset];
  if (patches)
    node.traverse((child) => {
      child.userData = remapPatchExtras(child.userData, patches);
    });
  if (part.group) {
    const rule = endpointPatchRule(part.node, availableNodes, group?.patches);
    if (rule) Object.assign(node.userData, patchBindingExtras(rule));
  }
}
