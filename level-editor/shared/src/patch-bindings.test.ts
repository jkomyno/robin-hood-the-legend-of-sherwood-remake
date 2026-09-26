import test from "node:test";
import assert from "node:assert/strict";
import { patchBindingExtras, patchBindingsFromMetadata } from "./patch-bindings.ts";

test("publication metadata yields only active placement patch rules", () => {
  const bindings = patchBindingsFromMetadata({
    Wall: {
      reveal_role: "shared",
      reveal_patch_ids: [],
      sight_patch_before_ids: [],
      drawbridge_endpoint_source_sha256: "evidence",
    },
    Roof: {
      reveal_component_role: "removable-cover",
      reveal_hide_when_applied: ["patch-003"],
      reveal_show_when_applied: [],
    },
    Texture: { reveal_material_patch: "patch-005", reveal_material_state: "revealed" },
  });
  assert.deepEqual(bindings, {
    Roof: { hide: ["patch-003"] },
    Texture: { material: { patch: "patch-005", state: "revealed" } },
  });
  assert.deepEqual(patchBindingExtras(bindings!.Roof!), {
    reveal_hide_when_applied: ["patch-003"],
  });
  assert.deepEqual(patchBindingExtras({ material: { patch: "patch-005", state: "revealed" } }), {
    reveal_material_patch: "patch-005",
    reveal_material_state: "revealed",
  });
});
