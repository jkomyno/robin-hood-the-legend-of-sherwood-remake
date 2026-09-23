import * as THREE from "three";

export function isEffectivelyVisible(object: THREE.Object3D) {
  for (let node: THREE.Object3D | null = object; node; node=node.parent)
    if (!node.visible) return false;
  return true;
}

/** Patch appearance previews use reviewed graphics/covers, independently of sight geometry. */
export class PatchDisplay {
  private readonly revealed = new Set<string>();
  set(patch: string, revealed: boolean) {
    if (!patch) throw new Error("Patch ID is required");
    if (revealed) this.revealed.add(patch); else this.revealed.delete(patch);
  }
  clear() { this.revealed.clear(); }
  isRevealed(patch: string) { return this.revealed.has(patch); }
  apply(root: THREE.Object3D) {
    root.traverse(object => {
      const {reveal_material_patch: patch, reveal_material_state: state, reveal_hide_when_applied: hide} = object.userData;
      if (patch !== undefined || state !== undefined) {
        if (typeof patch !== "string" || !patch || (state !== "covered" && state !== "revealed"))
          throw new Error("Invalid exported patch material state");
        object.visible = (state === "revealed") === this.revealed.has(patch);
      } else if (hide !== undefined) {
        if (!Array.isArray(hide) || hide.some(id => typeof id !== "string" || !id))
          throw new Error("Invalid reviewed patch cover IDs");
        object.visible = !hide.some(id => this.revealed.has(id));
      }
    });
  }
}
