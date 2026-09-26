import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { PatchDisplay, isEffectivelyVisible } from "./patch-display.ts";

test("patch state selects one material alternative and hides only reviewed covers", () => {
  const root = new THREE.Group(),
    covered = new THREE.Group(),
    revealed = new THREE.Group(),
    roof = new THREE.Group(),
    unrelated = new THREE.Group();
  covered.userData = { reveal_material_patch: "patch-000", reveal_material_state: "covered" };
  revealed.userData = { reveal_material_patch: "patch-000", reveal_material_state: "revealed" };
  roof.userData = { reveal_hide_when_applied: ["patch-000"] };
  unrelated.userData = { sight_patch_before_ids: ["patch-000"] };
  root.add(covered, revealed, roof, unrelated);
  const display = new PatchDisplay();
  display.apply(root);
  assert.deepEqual(
    root.children.map((o) => o.visible),
    [true, false, true, true],
  );
  display.set("patch-000", true);
  display.apply(root);
  assert.deepEqual(
    root.children.map((o) => o.visible),
    [false, true, false, true],
  );
  const roofMesh = new THREE.Mesh();
  roof.add(roofMesh);
  assert.equal(isEffectivelyVisible(roofMesh), false);
  display.set("patch-other", true);
  display.set("patch-000", false);
  display.apply(root);
  assert.deepEqual(
    root.children.map((o) => o.visible),
    [true, false, true, true],
  );
});

test("malformed material states fail instead of displaying both alternatives", () => {
  const root = new THREE.Group();
  root.userData = { reveal_material_patch: "patch-000", reveal_material_state: "unknown" };
  assert.throws(() => new PatchDisplay().apply(root), /Invalid exported/);
});

test("revealed-only receivers show for any reviewed trigger and reset without changing user-hidden parents", () => {
  const root = new THREE.Group(),
    receiver = new THREE.Group(),
    hiddenParent = new THREE.Group();
  receiver.userData = { reveal_show_when_applied: ["patch-000", "patch-001"] };
  const child = new THREE.Mesh();
  receiver.add(child);
  root.add(receiver, hiddenParent);
  hiddenParent.visible = false;
  const hiddenReceiver = receiver.clone(true);
  hiddenParent.add(hiddenReceiver);
  const display = new PatchDisplay();
  display.apply(root);
  assert.equal(isEffectivelyVisible(child), false);
  display.set("patch-other", true);
  display.apply(root);
  assert.equal(receiver.visible, false);
  display.set("patch-001", true);
  display.apply(root);
  assert.equal(isEffectivelyVisible(child), true);
  assert.equal(isEffectivelyVisible(hiddenReceiver), false);
  display.set("patch-000", true);
  display.set("patch-001", false);
  display.apply(root);
  assert.equal(receiver.visible, true);
  display.clear();
  display.apply(root);
  assert.equal(receiver.visible, false);
});

test("receiver visibility composes with material alternatives and rejects malformed triggers", () => {
  const root = new THREE.Group();
  root.userData = {
    reveal_material_patch: "patch-000",
    reveal_material_state: "revealed",
    reveal_show_when_applied: ["patch-001"],
  };
  const display = new PatchDisplay();
  display.set("patch-000", true);
  display.apply(root);
  assert.equal(root.visible, false);
  display.set("patch-001", true);
  display.apply(root);
  assert.equal(root.visible, true);
  for (const triggers of [[], "patch-000", [null], [""]]) {
    root.userData = { reveal_show_when_applied: triggers };
    assert.throws(() => display.apply(root), /Invalid reviewed patch receiver/);
  }
});
