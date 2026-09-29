import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { gameToScene } from "@rle/shared";
import {
  movementTransitionCompilerFixture,
  joinedTransitionCompilerFixture,
} from "../../shared/test-fixtures/asset-gameplay.ts";
import { validateAssetGameplay } from "../../shared/src/asset-gameplay.ts";
import {
  bindBakeAppearances,
  planAppearanceRegions,
  bakeAppearanceRegions,
} from "./map-appearance-bake.ts";
import { compileMap, type BakeBounds } from "./map-compile.ts";
import { contentBakeBounds } from "./map-bake-render.ts";

const camera = movementTransitionCompilerFixture().document.camera;
const bounds: BakeBounds = [0, 0, 100, 100];
function mesh(x: number, y: number, patch: string) {
  const geometry = new THREE.BufferGeometry().setFromPoints(
    [
      [x, y],
      [x + 10, y],
      [x, y + 10],
    ].map(([px, py]) => new THREE.Vector3(...gameToScene(camera, px!, py!, 0))),
  );
  const node = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial());
  node.userData.reveal_show_when_applied = [patch];
  node.visible = false;
  return node;
}
function scene() {
  const root = new THREE.Group();
  root.add(mesh(10, 10, "a"), mesh(70, 70, "b"));
  return root;
}
const transitions = [{ id: "a" }, { id: "b" }];

test("appearance planning includes hidden variants and merges intersecting dependencies", () => {
  const root = scene();
  assert.deepEqual(
    planAppearanceRegions(root, camera, bounds, transitions, false).map((p) => p.patches),
    [["a"], ["b"]],
  );
  const overlap = mesh(15, 15, "b");
  root.add(overlap);
  const plans = planAppearanceRegions(root, camera, bounds, transitions, false);
  assert.equal(plans.length, 1);
  assert.deepEqual(plans[0]!.patches, ["a", "b"]);
  assert.ok(plans[0]!.bounds[0] <= 10 && plans[0]!.bounds[2] >= 70);
  root.remove(overlap);
  assert.deepEqual(planAppearanceRegions(root, camera, bounds, transitions, true), [
    { bounds, patches: ["a", "b"] },
  ]);
});

test("appearance planning respects hidden owners and validates bindings and state budgets", () => {
  const root = scene();
  const hidden = new THREE.Group();
  hidden.visible = false;
  hidden.add(mesh(0, 0, "unbound"));
  root.add(hidden);
  const frame = contentBakeBounds(root, camera, true);
  assert.ok(frame[0] >= 9 && frame[1] >= 9);
  assert.ok(frame[0] + frame[2] >= 80 && frame[1] + frame[3] >= 80);
  assert.equal(planAppearanceRegions(root, camera, bounds, transitions, false).length, 2);
  hidden.visible = true;
  assert.throws(() => planAppearanceRegions(root, camera, bounds, transitions, false), /Unbound/);
  root.remove(hidden);
  assert.throws(
    () => planAppearanceRegions(root, camera, [0, 0, 8000, 8000], transitions, true),
    /64 megapixels/,
  );
});

test("appearance combinations crop full-frame fields and restore initial state after failures", () => {
  const root = scene();
  const plans = planAppearanceRegions(root, camera, bounds, transitions, false);
  const render = () => {
    const state = Number(root.children[0]!.visible) + 2 * Number(root.children[1]!.visible);
    return {
      color: new Uint8Array(100 * 100 * 4).fill(state),
      depth: Uint16Array.from({ length: 10000 }, (_, i) => i + state),
    };
  };
  const images = bakeAppearanceRegions(root, plans, 100, render(), render);
  assert.equal(images[0]!.states[1]!.color[0], 1);
  assert.equal(images[1]!.states[1]!.color[0], 2);
  for (const image of images) {
    const [x, y, w, h] = image.bounds;
    assert.equal(image.states[0]!.depth[0], y * 100 + x);
    assert.equal(image.states[0]!.depth.length, w * h);
    assert.equal(image.states[0]!.depth[w], (y + 1) * 100 + x);
  }
  assert.ok(root.children.every((node) => !node.visible));
  assert.throws(
    () =>
      bakeAppearanceRegions(root, plans, 100, render(), () => {
        throw new Error("GPU failed");
      }),
    /GPU failed/,
  );
  assert.ok(root.children.every((node) => !node.visible));
});

test("asset-local appearance bindings follow duplicated placements and reject missing definitions", () => {
  const { document, assets, hut } = movementTransitionCompilerFixture();
  hut.gameplay!.movementTransitions![0]!.appearances = ["roof"];
  const copy = structuredClone(document.objects[0]!);
  copy.id = "hut-b-body";
  copy.group = "hut-b";
  copy.transform.dx += 500;
  document.objects.push(copy);
  document.groups.push({ ...structuredClone(document.groups[0]!), id: "hut-b" });
  const compiled = compileMap(document, [0, 0, 2000, 2000], assets);
  const transitions = compiled.descriptor.asset_geometry!.movement_transitions!;
  const root = new THREE.Group();
  for (const id of ["hut-a-body", "hut-b-body"]) {
    const wrapper = new THREE.Group();
    wrapper.userData.map_bake_object_id = id;
    wrapper.add(mesh(0, 0, "roof"));
    root.add(wrapper);
  }
  const unbound = root.clone(true);
  bindBakeAppearances(root, document, assets, transitions);
  assert.deepEqual(
    root.children.map((wrapper) => wrapper.children[0]!.userData.reveal_show_when_applied),
    [["hut-a/hut/barriers"], ["hut-b/hut/barriers"]],
  );
  document.groups[0]!.patches = { hut: { roof: "preview-a" } };
  document.groups[1]!.patches = { hut: { roof: "preview-b" } };
  const preview = unbound.clone(true);
  preview.children[0]!.children[0]!.userData.reveal_show_when_applied = ["preview-a"];
  preview.children[1]!.children[0]!.userData.reveal_show_when_applied = ["preview-b"];
  const remapped = compileMap(document, [0, 0, 2000, 2000], assets);
  bindBakeAppearances(
    preview,
    document,
    assets,
    remapped.descriptor.asset_geometry!.movement_transitions!,
  );
  assert.deepEqual(
    preview.children.map((wrapper) => wrapper.children[0]!.userData.reveal_show_when_applied),
    [["hut-a/hut/barriers"], ["hut-b/hut/barriers"]],
  );
  document.groups[1]!.patches = { hut: { roof: "preview-a" } };
  assert.throws(
    () => compileMap(document, [0, 0, 2000, 2000], assets),
    /joined gameplay transition/,
  );
  delete hut.gameplay!.movementTransitions![0]!.appearances;
  assert.throws(
    () => bindBakeAppearances(unbound, document, assets, transitions),
    /Missing asset gameplay binding/,
  );
  hut.gameplay!.movementTransitions![0]!.appearances = ["roof", "roof"];
  assert.throws(
    () => validateAssetGameplay(hut.gameplay, hut),
    /multiply controlled transition appearance/,
  );
});

test("asset contact joins bind both appearances and detach when a member moves", () => {
  const { document, assets, wing, wingPart } = joinedTransitionCompilerFixture();
  const compile = () =>
    compileMap(document, [0, 0, 2000, 2000], assets).descriptor.asset_geometry!
      .movement_transitions!;
  const joined = compile();
  assert.equal(joined.length, 1);
  assert.deepEqual(joined[0]!.aliases, ["wing/wing/barriers"]);
  assert.equal(joined[0]!.initial_sight!.length, 2);
  assert.equal(joined[0]!.applied_sight!.length, 2);
  const bind = (transitions: ReturnType<typeof compile>) => {
    const root = new THREE.Group();
    for (const id of ["hut-a-body", "wing-body"]) {
      const wrapper = new THREE.Group();
      wrapper.userData.map_bake_object_id = id;
      wrapper.add(mesh(0, 0, "preview-roof"));
      root.add(wrapper);
    }
    bindBakeAppearances(root, document, assets, transitions);
    return root.children.map((wrapper) => wrapper.children[0]!.userData.reveal_show_when_applied);
  };
  assert.deepEqual(bind(joined), [[joined[0]!.id], [joined[0]!.id]]);
  wingPart.transform.dx += 1;
  const separate = compile();
  assert.equal(separate.length, 2);
  assert.deepEqual(bind(separate), [["hut-a/hut/barriers"], ["wing/wing/barriers"]]);
  wingPart.transform.dx -= 1;
  const copies = document.objects
    .filter((p) => p.group)
    .map((p) => {
      const copy = structuredClone(p);
      copy.id += "-copy";
      copy.group += "-copy";
      copy.transform.dy += 500;
      return copy;
    });
  document.objects.push(...copies);
  document.groups.push(
    ...document.groups.map((g) => ({ ...structuredClone(g), id: `${g.id}-copy` })),
  );
  const duplicated = compile();
  assert.equal(duplicated.length, 2);
  assert.deepEqual(
    new Set(duplicated.flatMap((t) => t.aliases!)),
    new Set(["wing/wing/barriers", "wing-copy/wing/barriers"]),
  );
  wing.gameplay!.movementTransitions![0]!.definitive = true;
  assert.throws(compile, /identical world triggers/);
  wing.gameplay!.movementTransitions![0]!.join!.point[0] = NaN;
  assert.throws(compile, /invalid transition join anchor/);
});
