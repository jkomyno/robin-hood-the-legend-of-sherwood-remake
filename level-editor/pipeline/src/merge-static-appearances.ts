import type { Scene } from "@gltf-transform/core";
import { remapPatchExtras, type AppearancePatches } from "@rle/shared";
import { canonical } from "./bundle-asset-states.ts";

/** Give each constituent's display rules a distinct local namespace, preserving resolved behavior. */
export function mergeStaticAppearances(
  scene: Scene,
  asset: string,
  patches: AppearancePatches | undefined,
): Record<string, string> {
  if (patches && Object.keys(patches).some((key) => key !== asset))
    throw new Error("Static merge cannot migrate another asset's appearance bindings");
  const bindings = patches?.[asset] ?? {};
  if (bindings.state !== undefined)
    throw new Error("Variant state bindings require explicit migration");
  const locals = new Set<string>();
  scene.traverse((node) => {
    const extras = node.getExtras();
    for (const field of ["reveal_hide_when_applied", "reveal_show_when_applied"] as const) {
      const ids = extras[field];
      if (ids === undefined) continue;
      if (!Array.isArray(ids) || ids.some((id) => typeof id !== "string"))
        throw new Error("Invalid appearance trigger metadata");
      ids.forEach((id: string) => locals.add(id));
    }
    if (extras.reveal_material_patch !== undefined) {
      if (typeof extras.reveal_material_patch !== "string")
        throw new Error("Invalid material appearance trigger");
      locals.add(extras.reveal_material_patch);
    }
  });
  if (Object.keys(bindings).some((key) => !locals.has(key)))
    throw new Error("Appearance binding has no model trigger");
  const mapping = Object.fromEntries([...locals].map((key) => [key, `${asset}/${key}`]));
  const mergedBindings = Object.fromEntries(
    Object.entries(bindings).map(([key, value]) => [mapping[key]!, value]),
  );
  scene.traverse((node) => {
    const before = node.getExtras();
    const after = remapPatchExtras(before, mapping);
    // Unbound appearances remain local, so compare only bindings supplied by the scene.
    const resolvedBefore = remapPatchExtras(before, { ...mapping, ...bindings });
    const resolvedAfter = remapPatchExtras(after, mergedBindings);
    if (canonical(resolvedBefore) !== canonical(resolvedAfter))
      throw new Error("Static merge changed appearance behavior");
    node.setExtras(after);
  });
  return mergedBindings;
}
