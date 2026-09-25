import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { listProjectionAssets, prepareProjectionAsset } from "./projection-library.ts";
import { disposeObjectResources } from "./resources.ts";
import { insertProjectionAsset } from "./asset-commands.ts";
import { prepareMapCandidate } from "./map-candidate.ts";
import type { Level3D } from "@rle/shared";

function fixture() {
  const obstacle = { points: [{ x: 0, y: 0, z_bottom: 0, z_top: 10 }, { x: 10, y: 0, z_bottom: 0, z_top: 10 }, { x: 0, y: 10, z_bottom: 0, z_top: 10 }],
    opaque: true, solid: true, mouse: true, show_shadow_polygon: true, default_material: 0, material_indices: [], projection_area: null };
  const descriptor = { version: 1, kind: "projection-mapped-asset", id: "house", name: "House", source_map: "Leicester", model: "model.glb",
    source_origin_scene: [20, -40, 0], source_origin_game: [20, 23, 0], parts: [{ node: "building-000", name: "Wall", source_obstacle: 0, obstacle_local_game: obstacle }] };
  const entry = { id: "house", name: "House", source_map: "Leicester", descriptor: "3d-assets/house/asset.json", model: "3d-assets/house/model.glb" };
  const files = new Map<string, File>();
  const json = (path: string, value: unknown) => files.set(path, new File([JSON.stringify(value)], path));
  json(entry.descriptor, descriptor);
  files.set(entry.model, new File([new Uint8Array([3, 2, 1])], "model.glb"));
  json("3d-assets/index.json", { version: 1, assets: [{ ...entry, descriptor: "house/asset.json", model: "house/model.glb" },
    { id: "york-house", name: "York House", source_map: "York", descriptor: "york/asset.json", model: "york/model.glb" }] });
  const handle = (prefix: string): FileSystemDirectoryHandle => ({
    async getDirectoryHandle(name: string) {
      const next = `${prefix}${name}/`;
      if (![...files.keys()].some(key => key.startsWith(next))) throw new DOMException(next, "NotFoundError");
      return handle(next);
    },
    async getFileHandle(name: string) {
      const file = files.get(prefix + name);
      if (!file) throw new DOMException(name, "NotFoundError");
      return { getFile: async () => file };
    },
    async *entries() {
      for (const path of files.keys()) if (path.startsWith(prefix) && !path.slice(prefix.length).includes("/")) yield [path.slice(prefix.length), { kind: "file" }];
    },
  }) as unknown as FileSystemDirectoryHandle;
  const asset = new THREE.Group(), root = new THREE.Group(), group = new THREE.Group();
  root.name = "map"; group.userData.asset_group = "house";
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshBasicMaterial());
  mesh.name = "building-000"; mesh.userData.source_obstacle = 0;
  asset.add(root); root.add(group); group.add(mesh);
  let disposed = 0; mesh.geometry.addEventListener("dispose", () => disposed++);
  return { files, json, entry, descriptor, directory: handle(""), asset, group, mesh, disposed: () => disposed };
}

test("standalone index filters the current map and actual model parts receive namespaced keys", async (t) => {
  const f = fixture();
  assert.deepEqual(await listProjectionAssets(f.directory, "leicester"), [f.entry]);
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: f.asset }));
  const prepared = await prepareProjectionAsset(f.directory, f.entry, "Leicester");
  assert.equal(prepared.sources.get("asset:house:building-000"), f.mesh);
  assert.match(prepared.reference.model_sha256, /^[a-f0-9]{64}$/);
  assert.equal(f.disposed(), 0);
  disposeObjectResources([prepared.asset]);
  assert.equal(f.disposed(), 1);
});

test("changed files reject before model publication; bad model cleanup is owned", async (t) => {
  const f = fixture();
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: f.asset }));
  const prepared = await prepareProjectionAsset(f.directory, f.entry, "Leicester");
  assert.equal((await prepareProjectionAsset(f.directory, f.entry, "York")).descriptor.source_map, "Leicester");
  await assert.rejects(prepareProjectionAsset(f.directory, f.entry, "Leicester", { ...prepared.reference, model_sha256: "c".repeat(64) }), /model changed/);
  f.json(f.entry.descriptor, { ...f.descriptor, name: "Edited" });
  await assert.rejects(prepareProjectionAsset(f.directory, f.entry, "Leicester", prepared.reference), /descriptor changed/);
  disposeObjectResources([prepared.asset]);
  const bad = fixture(); bad.mesh.userData.source_obstacle = 12;
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: bad.asset }));
  await assert.rejects(prepareProjectionAsset(bad.directory, bad.entry, "Leicester"), /Unexpected/);
  assert.equal(bad.disposed(), 1);
});

test("saved external models reload before document validation and retire with their map", async (t) => {
  const f = fixture();
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: f.asset }));
  const prepared = await prepareProjectionAsset(f.directory, f.entry, "Leicester");
  const base: Level3D = { version: 1, map: "York", size: [100, 100], camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    glb: "York-volumes.scene.glb", groups: [], objects: [] };
  const inserted = insertProjectionAsset(base, prepared.descriptor, prepared.reference, [50, 50, 0]);
  f.json("scenes/York.level3d.json", inserted.document);
  f.json("scenes/York-volumes.scene.json", { version: 1, map: "York", size: [100, 100], camera: base.camera, placements: [] });
  f.files.set("scenes/York-volumes.scene.glb", new File([new Uint8Array([7])], "map.glb"));
  const map = new THREE.Group(); let calls = 0;
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: calls++ === 0 ? map : f.asset }));
  const candidate = await prepareMapCandidate("York", f.directory, null);
  assert.equal(calls, 2);
  assert.equal(candidate.sources.get("asset:house:building-000"), f.mesh);
  assert.equal(candidate.document.groups[0]!.transform.dx, 50);
  assert.deepEqual(candidate.document.assetSources, [prepared.reference]);
  disposeObjectResources([candidate.asset]);
  assert.equal(f.disposed(), 1);
});

test("static model variants load one endpoint, retain endpoint obstacles, and coexist on save/reload", async (t) => {
  const f = fixture();
  const appliedParts = [{ ...f.descriptor.parts[0]!, name: "Lowered deck", obstacle_local_game: {
    ...f.descriptor.parts[0]!.obstacle_local_game, solid: false,
  } }];
  f.json(f.entry.descriptor, { ...f.descriptor, state_variants: {
    initial: { name: "Raised", model: "model.glb" },
    applied: { name: "Lowered", model: "lowered.glb", parts: appliedParts },
  } });
  f.files.set("3d-assets/house/lowered.glb", new File([new Uint8Array([8, 9])], "lowered.glb"));
  const entries = await listProjectionAssets(f.directory, "Leicester");
  assert.deepEqual(entries.map(entry => entry.name), ["House — Raised (static)", "House — Lowered (static)"]);
  const loaded: number[][] = [];
  t.mock.method(GLTFLoader.prototype, "parseAsync", async (bytes: ArrayBuffer) => {
    loaded.push([...new Uint8Array(bytes)]);
    return { scene: f.asset };
  });
  const raised = await prepareProjectionAsset(f.directory, entries[0]!, "Leicester");
  const lowered = await prepareProjectionAsset(f.directory, entries[1]!, "Leicester");
  assert.deepEqual(loaded, [[3, 2, 1], [8, 9]]);
  assert.equal(lowered.reference.state_variant, "applied");
  assert.equal(lowered.descriptor.parts[0]!.obstacle_local_game.solid, false);
  assert.ok(lowered.sources.has("asset:house--state-applied:building-000"));
  let document: Level3D = { version: 1, map: "Leicester", size: [100, 100], camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    glb: "Leicester-volumes.scene.glb", groups: [], objects: [] };
  for (const prepared of [raised, lowered]) document = insertProjectionAsset(document, prepared.descriptor, prepared.reference, [50, 50, 0]).document;
  assert.equal(document.assetSources!.length, 2);
  assert.notEqual(document.objects[0]!.node, document.objects[1]!.node);
  const reloaded = await prepareProjectionAsset(f.directory, lowered.reference, "Leicester", lowered.reference);
  assert.deepEqual(reloaded.reference, lowered.reference);
  await assert.rejects(prepareProjectionAsset(f.directory, { ...entries[1]!, model: f.entry.model }, "Leicester"), /path mismatch/);
  f.files.set(lowered.reference.model, new File([new Uint8Array([7])], "lowered.glb"));
  await assert.rejects(prepareProjectionAsset(f.directory, lowered.reference, "Leicester", lowered.reference), /model changed/);
});

test("supplemental mission models retain profile provenance without inventing an obstacle index", async (t) => {
  const f = fixture();
  const { source_obstacle, ...part } = f.descriptor.parts[0]!;
  const mission = { ...part, node: "mission-second-drawbridge", mission_profile: "Derby - Pont_levis02" };
  f.json(f.entry.descriptor, { ...f.descriptor, parts: [mission] });
  f.mesh.name = mission.node;
  delete f.mesh.userData.source_obstacle;
  f.mesh.userData.mission_patch_profile = mission.mission_profile;
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: f.asset }));
  const prepared = await prepareProjectionAsset(f.directory, f.entry, "Leicester");
  const base: Level3D = { version: 1, map: "Leicester", size: [100, 100], camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    glb: "map.glb", groups: [], objects: [] };
  const result = insertProjectionAsset(base, prepared.descriptor, prepared.reference, [0, 0, 0]);
  assert.equal(result.document.objects[0]!.kind, "mission");
  assert.deepEqual(result.document.objects[0]!.source, { map: "Leicester", mission_profile: mission.mission_profile });
  f.mesh.userData.source_obstacle = 267;
  await assert.rejects(prepareProjectionAsset(f.directory, f.entry, "Leicester"), /Unexpected/);
});

test("full-map mission metadata creates one source and saved deletions remain deleted", async (t) => {
  const f = fixture();
  f.group.userData.asset_name = "House";
  f.mesh.userData.part_name = "Wall";
  const bridgeGroup = new THREE.Group();
  bridgeGroup.userData = { asset_group: "second-drawbridge", asset_name: "Second drawbridge" };
  const bridge = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshBasicMaterial());
  bridge.name = "mission-second-drawbridge";
  bridge.userData = { part_name: "Raised endpoint", mission_patch_profile: "Derby - Pont_levis02",
    obstacle_local_game: f.descriptor.parts[0]!.obstacle_local_game };
  bridgeGroup.add(bridge); f.asset.children[0]!.add(bridgeGroup);
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: f.asset }));
  f.json("scenes/Leicester-volumes.scene.json", { version: 1, map: "Leicester", size: [100, 100],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 }, placements: [] });
  f.files.set("scenes/Leicester-volumes.scene.glb", new File([new Uint8Array([7])], "map.glb"));
  f.json("Leicester.rhp.json", { format: "Fullgame", misc: {}, sight_obstacles: [f.descriptor.parts[0]!.obstacle_local_game],
    patches: [], animations: [], material_sectors: [], light_sectors: [], elevation_lines: [], masks: [], sound_sources: [],
    jump_zones: [], jump_line_pairs: [], lifts: [], buildings: [], motion_data: { layers: [], graph_bytes: [] } });
  const candidate = await prepareMapCandidate("Leicester", f.directory, { maps: new Set(["Leicester"]), levelsDir: f.directory });
  assert.equal(candidate.document.objects.length, 2);
  assert.equal(candidate.document.groups.length, 2);
  assert.equal(candidate.sources.get(bridge.name), bridge);
  const part = candidate.document.objects.find(object => object.kind === "mission")!;
  assert.deepEqual(part.source, { map: "Leicester", mission_profile: "Derby - Pont_levis02" });
  assert.equal(part.group, "second-drawbridge");
  f.json("scenes/Leicester.level3d.json", candidate.document);
  const saved = await prepareMapCandidate("Leicester", f.directory, null);
  assert.equal(saved.document.objects.length, 2);
  f.json("scenes/Leicester.level3d.json", { ...candidate.document, objects: candidate.document.objects.map(object =>
    object.kind === "mission" ? { ...object, source: { map: "Leicester", mission_profile: "Wrong profile" } } : object) });
  await assert.rejects(prepareMapCandidate("Leicester", f.directory, null), /Mission source profile mismatch/);
  f.json("scenes/Leicester.level3d.json", { ...candidate.document,
    objects: candidate.document.objects.filter(object => object.kind !== "mission") });
  assert.equal((await prepareMapCandidate("Leicester", f.directory, null)).document.objects.length, 1);
  bridge.userData.source_obstacle = 267;
  await assert.rejects(prepareMapCandidate("Leicester", f.directory, null), /Invalid authored mission/);
});

test("shared catalog lists assets from every source level", async () => {
  const f = fixture();
  f.json("3d-assets/york/asset.json", { ...f.descriptor, id: "york-house", name: "York House", source_map: "York" });
  const entries = await listProjectionAssets(f.directory);
  assert.deepEqual(entries.map(entry => entry.source_map), ["Leicester", "York"]);
});

test("standalone component metadata must match the pinned scoped descriptor", async (t) => {
  const f=fixture();const name="building-000--component-west";
  f.json(f.entry.descriptor,{...f.descriptor,parts:[{...f.descriptor.parts[0],node:name,source_components:["west"]}]});
  f.mesh.name=name;f.mesh.userData.source_components=["west"];
  t.mock.method(GLTFLoader.prototype,"parseAsync",async()=>({scene:f.asset}));
  const prepared=await prepareProjectionAsset(f.directory,f.entry,"York");
  assert.ok(prepared.sources.has("asset:house:"+name));
  f.mesh.userData.source_components=["east"];
  await assert.rejects(prepareProjectionAsset(f.directory,f.entry,"York"),/Unexpected/);
});

test("additional complete variants retain the covered base and pin each endpoint on reload", async (t) => {
  const f=fixture();
  const endpointParts=[{...f.descriptor.parts[0]!,name:"Open door",obstacle_local_game:{...f.descriptor.parts[0]!.obstacle_local_game,solid:false}}];
  f.json(f.entry.descriptor,{...f.descriptor,standalone_variants:{initial:{name:"Door closed",model:"closed.glb"},applied:{name:"Door open",model:"open.glb",parts:endpointParts}}});
  f.files.set("3d-assets/house/closed.glb",new File([new Uint8Array([4])],"closed.glb"));
  f.files.set("3d-assets/house/open.glb",new File([new Uint8Array([5])],"open.glb"));
  const entries=await listProjectionAssets(f.directory,"Leicester");
  assert.deepEqual(entries.map(entry=>entry.id),["house","house--state-initial","house--state-applied"]);
  assert.equal(entries[0]!.model,f.entry.model);
  const loaded:number[][]=[];
  t.mock.method(GLTFLoader.prototype,"parseAsync",async(bytes:ArrayBuffer)=>{loaded.push([...new Uint8Array(bytes)]);return{scene:f.asset};});
  const base=await prepareProjectionAsset(f.directory,entries[0]!,"York");
  const initial=await prepareProjectionAsset(f.directory,entries[1]!,"York");
  const applied=await prepareProjectionAsset(f.directory,entries[2]!,"York");
  assert.deepEqual(loaded,[[3,2,1],[4],[5]]);
  assert.equal(base.reference.state_variant,undefined);
  assert.equal(initial.reference.state_variant,"initial");
  assert.equal(applied.descriptor.parts[0]!.obstacle_local_game.solid,false);
  assert.deepEqual((await prepareProjectionAsset(f.directory,applied.reference,"York",applied.reference)).reference,applied.reference);
  await assert.rejects(prepareProjectionAsset(f.directory,{...entries[2]!,model:f.entry.model},"York"),/path mismatch/);
});
