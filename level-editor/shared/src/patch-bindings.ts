/** Mission patch IDs attached to one placed asset, keyed by model node name. */
export interface PatchBinding {
  hide?: string[];
  show?: string[];
  material?: { patch: string; state: "covered" | "revealed" };
}

export type PatchBindings = Record<string, PatchBinding>;

/** Extract only placement-specific display rules from publication node metadata. */
export function patchBindingsFromMetadata(
  metadata: Record<string, Record<string, unknown>> | undefined,
): PatchBindings | undefined {
  if (!metadata) return undefined;
  const bindings: PatchBindings = {};
  for (const [node, values] of Object.entries(metadata)) {
    const binding: PatchBinding = {};
    const hide = values.reveal_hide_when_applied;
    const show = values.reveal_show_when_applied;
    if (Array.isArray(hide) && hide.length) binding.hide = [...hide];
    if (Array.isArray(show) && show.length) binding.show = [...show];
    if (typeof values.reveal_material_patch === "string") {
      binding.material = {
        patch: values.reveal_material_patch,
        state: values.reveal_material_state as "covered" | "revealed",
      };
    }
    if (Object.keys(binding).length) bindings[node] = binding;
  }
  return Object.keys(bindings).length ? bindings : undefined;
}

export function patchBindingExtras(binding: PatchBinding): Record<string, unknown> {
  return {
    ...(binding.hide ? { reveal_hide_when_applied: binding.hide } : {}),
    ...(binding.show ? { reveal_show_when_applied: binding.show } : {}),
    ...(binding.material
      ? {
          reveal_material_patch: binding.material.patch,
          reveal_material_state: binding.material.state,
        }
      : {}),
  };
}
