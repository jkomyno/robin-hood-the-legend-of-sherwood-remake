import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { PatchDisplay, isEffectivelyVisible } from "./patch-display.ts";

test("patch state selects one material alternative and hides only reviewed covers", () => {
  const root=new THREE.Group(), covered=new THREE.Group(), revealed=new THREE.Group(), roof=new THREE.Group(), unrelated=new THREE.Group();
  covered.userData={reveal_material_patch:"patch-000",reveal_material_state:"covered"};
  revealed.userData={reveal_material_patch:"patch-000",reveal_material_state:"revealed"};
  roof.userData={reveal_hide_when_applied:["patch-000"]};
  unrelated.userData={sight_patch_before_ids:["patch-000"]};
  root.add(covered,revealed,roof,unrelated);
  const display=new PatchDisplay();display.apply(root);
  assert.deepEqual(root.children.map(o=>o.visible),[true,false,true,true]);
  display.set("patch-000",true);display.apply(root);
  assert.deepEqual(root.children.map(o=>o.visible),[false,true,false,true]);
  const roofMesh=new THREE.Mesh();roof.add(roofMesh);
  assert.equal(isEffectivelyVisible(roofMesh),false);
  display.set("patch-other",true);display.set("patch-000",false);display.apply(root);
  assert.deepEqual(root.children.map(o=>o.visible),[true,false,true,true]);
});

test("malformed material states fail instead of displaying both alternatives", () => {
  const root=new THREE.Group();root.userData={reveal_material_patch:"patch-000",reveal_material_state:"unknown"};
  assert.throws(()=>new PatchDisplay().apply(root),/Invalid exported/);
});
