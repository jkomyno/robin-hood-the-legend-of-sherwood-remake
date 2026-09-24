import test from "node:test";
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
            glb: "York-volumes.scene.glb",
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
  return { directory, asset, mesh, buildings, disposals: () => disposals };
}

test("validated candidate retains ownership until accepted or rejected by its caller", async (t) => {
  const f = fixture();
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({
    scene: f.asset,
  }));
  const candidate = await prepareMapCandidate("York", f.directory, null);
  assert.equal(candidate.asset, f.asset);
  assert.equal(candidate.directory, f.directory);
  assert.equal(candidate.sources.get("building-000"), f.mesh);
  assert.equal(candidate.document.map, "York");
  assert.equal(candidate.saved, false); // New provenance must be saved, not silently acknowledged.
  assert.match(candidate.document.provenance!.glb_sha256!, /^[a-f0-9]{64}$/);
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
    /source map is Lincoln/,
  );
  disposeObjectResources([wrong.asset]);
});

test("invalid saved document releases the parsed asset before rejecting", async (t) => {
  const f = fixture({ version: 99 });
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({
    scene: f.asset,
  }));
  await assert.rejects(
    prepareMapCandidate("York", f.directory, null),
    /version/,
  );
  assert.equal(f.disposals(), 1);
});

test("duplicate reconstruction node identity rejects and deduplicates resource disposal", async (t) => {
  const f = fixture();
  f.buildings.add(f.mesh.clone());
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({
    scene: f.asset,
  }));
  await assert.rejects(
    prepareMapCandidate("York", f.directory, null),
    /Duplicate GLB node/,
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

test("GLB authored groups restore human names for pristine saved documents on any map", async (t) => {
  const f = authoredFixture();
  t.mock.method(GLTFLoader.prototype, "parseAsync", async () => ({ scene: f.asset }));
  const candidate = await prepareMapCandidate("York", f.directory, null);
  assert.equal(candidate.document.groups[0]!.id, "york-north-hall");
  assert.equal(candidate.document.groups[0]!.name, "North Hall");
  assert.equal(candidate.document.objects[0]!.name, "Hall walls");
  assert.equal(candidate.document.objects[0]!.group, "york-north-hall");
  assert.equal(candidate.saved, false);
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
  await assert.rejects(prepareMapCandidate("York", bad.directory, null), /Invalid authored GLB part metadata/);
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
