import test from "node:test";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { prepareMapCandidate } from "./map-candidate.ts";
import { disposeObjectResources } from "./resources.ts";

function fixture(saved: unknown = {}, map = "York", standalone = false) {
  const scene = {
    version: 1,
    standalone,
    map,
    size: [100, 200],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    placements: [],
  };
  const files = new Map([
    [
      "York-volumes.scene.json",
      new File([JSON.stringify(scene)], "scene.json"),
    ],
    [
      "York-volumes.scene.glb",
      new File([new Uint8Array([1, 2, 3])], "scene.glb"),
    ],
    [
      "York.level3d.json",
      new File(
        [
          JSON.stringify({
            ...scene,
            sceneAssets: [{ id: "base", role: "objects", model: "York-volumes.scene.glb", model_sha256: createHash("sha256").update(new Uint8Array([1,2,3])).digest("hex"), resources: [] }],
            sourceMap: standalone ? undefined : map,
            groups: [],
            objects: [],
            ...(saved as object),
          }),
        ],
        "document.json",
      ),
    ],
  ]);
  const directory = {
    async getDirectoryHandle() {
      return this;
    },
    async getFileHandle(name: string) {
      const file = files.get(name);
      if (!file) throw new DOMException(name, "NotFoundError");
      return { getFile: async () => file };
    },
    async *entries() {
      for (const name of files.keys()) yield [name, { kind: "file" }];
    },
  } as unknown as FileSystemDirectoryHandle;
  const asset = new THREE.Group();
  const buildings = new THREE.Group();
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(),
    new THREE.MeshBasicMaterial(),
  );
  mesh.name = "building-000";
  buildings.add(mesh);
  asset.add(buildings);
  let disposals = 0;
  mesh.geometry.addEventListener("dispose", () => disposals++);
  return { directory, files, asset, mesh, buildings, disposals: () => disposals };
}

test("validated candidate retains ownership until accepted or rejected by its caller", async (t) => {
  const f = fixture();
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({
    scene: f.asset,
  }));
  const candidate = await prepareMapCandidate("York", f.directory, null);
  assert.ok(candidate.asset.children.includes(f.asset));
  assert.equal(candidate.directory, f.directory);
  assert.equal(candidate.sources.get("building-000"), f.mesh);
  assert.equal(candidate.document.map, "York");
  assert.equal(candidate.saved, true);
  assert.equal(f.disposals(), 0);
  disposeObjectResources([candidate.asset]); // Same path used for a stale prepared load.
  assert.equal(f.disposals(), 1);
});

test("map source identity remains case-insensitive but never accepts a different map", async (t) => {
  const f = fixture({}, "yOrK");
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({
    scene: f.asset,
  }));
  const candidate = await prepareMapCandidate("York", f.directory, null);
  assert.equal(candidate.document.map, "yOrK");
  disposeObjectResources([candidate.asset]);
  const wrong = fixture({}, "Lincoln");
  await assert.rejects(
    prepareMapCandidate("York", wrong.directory, null),
    /expected source York/,
  );
  disposeObjectResources([wrong.asset]);
});

test("invalid saved document rejects before reading geometry", async (t) => {
  const f = fixture({ version: 99 });
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({
    scene: f.asset,
  }));
  await assert.rejects(
    prepareMapCandidate("York", f.directory, null),
    /version/,
  );
  assert.equal(f.disposals(), 0);
  disposeObjectResources([f.asset]);
});

test("duplicate reconstruction node identity rejects and deduplicates resource disposal", async (t) => {
  const f = fixture();
  f.buildings.add(f.mesh.clone());
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({
    scene: f.asset,
  }));
  await assert.rejects(
    prepareMapCandidate("York", f.directory, null),
    /Duplicate scene source node/,
  );
  assert.equal(f.disposals(), 1);
});

function authoredFixture(customName?: string) {
  const part = {
    id: "building-000", node: "building-000", kind: "building", source: { map: "York", obstacle: 0 },
    obstacle: { points: [{ x: 0, y: 0, z_bottom: 0, z_top: 10 }, { x: 10, y: 0, z_bottom: 0, z_top: 10 }, { x: 0, y: 10, z_bottom: 0, z_top: 10 }],
      opaque: true, solid: true, mouse: true, show_shadow_polygon: true, default_material: 0, material_indices: [], projection_area: null },
    transform: { dx: 0, dy: 0, dz: 0, rot_deg: 0 }, group: "group-000", ...(customName ? { name: customName } : {}),
  };
  const f = fixture({ objects: [part], groups: [{ id: "group-000", transform: { dx: 0, dy: 0, dz: 0, rot_deg: 0 } }] });
  f.buildings.name = "North_Hall";
  f.buildings.userData = { asset_group: "york-north-hall", name: "North Hall" };
  f.mesh.userData = { source_obstacle: 0, part_name: "Hall walls" };
  return f;
}

test("manifest ownership is authoritative and never silently regrouped while loading", async t => {
  const f=authoredFixture();
  const before=JSON.parse(await f.files.get("York.level3d.json")!.text());
  t.mock.method(GLTFLoader.prototype,"parseAsync",async()=>({scene:f.asset}));
  const candidate=await prepareMapCandidate("York",f.directory,null);
  assert.deepEqual(candidate.document,before);
  assert.equal(candidate.saved,true);
  disposeObjectResources([candidate.asset]);
});

test("authored exports preserve saved user names and reject mismatched canonical metadata", async (t) => {
  const f = authoredFixture("Custom wall");
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: f.asset }));
  const candidate = await prepareMapCandidate("York", f.directory, null);
  assert.equal(candidate.document.objects[0]!.name, "Custom wall");
  assert.equal(candidate.document.objects[0]!.group, "group-000");
  disposeObjectResources([candidate.asset]);
  const bad = authoredFixture();
  bad.mesh.userData.source_obstacle = 99;
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: bad.asset }));
  await assert.rejects(prepareMapCandidate("York", bad.directory, null), /Source obstacle mismatch/);
  assert.equal(bad.disposals(), 1);
});

test("authored standalone scenes open without a matching datadir level", async (t) => {
  const f = fixture({}, "York", true);
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: f.asset }));
  const candidate = await prepareMapCandidate("York", f.directory, { maps: new Set(), levelsDir: f.directory });
  assert.equal(candidate.level, null);
  assert.equal(candidate.document.map, "York");
  disposeObjectResources([candidate.asset]);
});

function parallelFixture(count: number) {
  const f = fixture();
  const hash = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
  const references = Array.from({ length: count }, (_, i) => {
    const id = `asset-${i}`, model = `${id}.glb`, descriptor = `${id}.json`;
    const bytes = new Uint8Array([100 + i]);
    const descriptorBytes = new TextEncoder().encode(JSON.stringify({
      version: 1, kind: "projection-mapped-asset", id, name: id, source_map: "Derby", model,
      source_origin_scene: [0,0,0], source_origin_game: [0,0,0],
      parts: [{ node: "building-000", name: id, source_obstacle: 0, obstacle_local_game: {
        points: [{x:0,y:0,z_bottom:0,z_top:10},{x:10,y:0,z_bottom:0,z_top:10},{x:0,y:10,z_bottom:0,z_top:10}],
        solid:true, opaque:true, mouse:true, show_shadow_polygon:false, default_material:0, material_indices:[], projection_area:null,
      }}],
    }));
    f.files.set(model, new File([bytes], model));
    f.files.set(descriptor, new File([descriptorBytes], descriptor));
    return { id, model, descriptor, model_sha256:hash(bytes), descriptor_sha256:hash(descriptorBytes) };
  });
  const saved = {version:1,map:"York",size:[100,200],camera:{kind:"oblique-orthographic",elevation_deg:35},sceneAssets: [{ id:"base",role:"objects",model:"York-volumes.scene.glb",model_sha256:hash(new Uint8Array([1,2,3])),resources:[] }],groups:[],objects:[],assetSources:references};
  f.files.set("York.level3d.json", new File([JSON.stringify(saved)], "document.json"));
  const pending = new Map<number, {resolve():void; reject(error:Error):void}>();
  const retired: number[] = [];
  let active = 0, peak = 0;
  const started: number[] = [];
  const parse = async (bytes: ArrayBuffer) => {
    if (bytes.byteLength === 3) return {scene:f.asset};
    const i = new Uint8Array(bytes)[0]! - 100;
    started.push(i); active++; peak=Math.max(peak,active);
    await new Promise<void>((resolve,reject)=>pending.set(i,{resolve,reject})).finally(()=>active--);
    const scene=new THREE.Group(),root=new THREE.Group(),group=new THREE.Group();
    root.name="map";group.userData.asset_group=`asset-${i}`;scene.add(root);root.add(group);
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshBasicMaterial());
    mesh.name="building-000";mesh.userData.source_obstacle=0;group.add(mesh);
    mesh.geometry.addEventListener("dispose",()=>retired.push(i));
    return {scene};
  };
  return {...f,pending,retired,started,parse,peak:()=>peak};
}
async function untilLoaded(check:()=>boolean) {
  for(let i=0;i<500;i++) {
    if(check())return;
    await new Promise(resolve=>setTimeout(resolve,1));
  }
  assert.fail("Timed out waiting for controlled model loads");
}

test("external assets load four at a time and preserve document order", async t => {
  const f=parallelFixture(7);
  t.mock.method(GLTFLoader.prototype,"parseAsync",f.parse);
  const load=prepareMapCandidate("York",f.directory,null);
  await untilLoaded(()=>f.pending.size===4);
  assert.deepEqual([...f.started].sort(),[0,1,2,3]);
  f.pending.get(2)!.resolve();
  await untilLoaded(()=>f.pending.has(4));
  f.pending.get(4)!.resolve();
  await untilLoaded(()=>f.pending.has(5));
  f.pending.get(5)!.resolve();
  await untilLoaded(()=>f.pending.has(6));
  for(const job of f.pending.values())job.resolve();
  const candidate=await load;
  assert.equal(f.peak(),4);
  assert.deepEqual([...candidate.sources.keys()].slice(1),Array.from({length:7},(_,i)=>`asset:asset-${i}:building-000`));
  assert.equal(f.retired.length,0);
  disposeObjectResources([candidate.asset]);
  assert.deepEqual(f.retired.sort(),[0,1,2,3,4,5,6]);
});

test("failed parallel loads stop scheduling and retire late completions before rejecting", async t => {
  const f=parallelFixture(7);
  t.mock.method(GLTFLoader.prototype,"parseAsync",f.parse);
  let settled=false;
  const load=prepareMapCandidate("York",f.directory,null);
  const rejected=assert.rejects(load,/model decode failed/).then(()=>{settled=true;});
  await untilLoaded(()=>f.pending.size===4);
  f.pending.get(1)!.reject(new Error("model decode failed"));
  await new Promise(resolve=>setTimeout(resolve,10));
  assert.equal(settled,false,"in-flight assets must settle before resource retirement");
  for(const [i,job] of f.pending)if(i!==1)job.resolve();
  await rejected;
  assert.equal(f.started.length,4);
  assert.equal(f.disposals(),1);
  assert.deepEqual(f.retired.sort(),[0,2,3]);
});

test("component exports restore scoped group ownership and reject missing footprints", async (t) => {
  const f=authoredFixture();
  const document=JSON.parse(await f.files.get("York.level3d.json")!.text());
  const name="building-000--component-west";
  document.objects[0].node=name;document.objects[0].id=name;document.objects[0].source.components=["west"];
  f.files.set("York.level3d.json",new File([JSON.stringify(document)],"York.level3d.json"));
  f.mesh.name=name;f.mesh.userData.source_components=["west"];f.mesh.userData.obstacle_local_game=document.objects[0].obstacle;
  t.mock.method(GLTFLoader.prototype,"parseAsync",async()=>({scene:f.asset}));
  const candidate=await prepareMapCandidate("York",f.directory,null);
  assert.equal(candidate.document.objects[0]!.group,"group-000");
  assert.deepEqual(candidate.document.objects[0]!.source.components,["west"]);
  delete f.mesh.userData.obstacle_local_game;
  await assert.rejects(prepareMapCandidate("York",f.directory,null),/Missing component footprint/);
});
