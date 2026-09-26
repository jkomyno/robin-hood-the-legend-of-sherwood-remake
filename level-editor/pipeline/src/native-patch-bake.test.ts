import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { IDENTITY_TRANSFORM, type Level3D } from "@rle/shared";
import { preserveNativePatchPreviews } from "./native-patch-bake.ts";

const sha = (bytes: Buffer) => crypto.createHash("sha256").update(bytes).digest("hex");
function fixture() {
  const profile = "Derby - Pont_levis02";
  const mission = Buffer.from(
    JSON.stringify({
      header: { map_filename: "Derby" },
      mission_patches: [
        {
          start_animation_valid: true,
          element_fx: { active: true, sprite: { profile_name: profile } },
        },
      ],
    }),
  );
  const obstacle = {
    points: [
      { x: 0, y: 0, z_bottom: 0, z_top: 10 },
      { x: 1, y: 0, z_bottom: 0, z_top: 10 },
      { x: 0, y: 1, z_bottom: 0, z_top: 10 },
    ],
    opaque: false,
    solid: false,
    mouse: false,
    show_shadow_polygon: false,
    default_material: 0,
    material_indices: [],
    projection_area: null,
  };
  const nodes = [
    { name: "Bridge", children: [1], extras: { asset_group: "bridge" } },
    {
      name: "mission-bridge",
      extras: {
        mission_patch_profile: profile,
        obstacle_local_game: obstacle,
        native_patch_preview: {
          mission: "H03_Der_MK",
          mission_sha256: sha(mission),
          patch_index: 0,
          profile,
          state: "initial",
        },
      },
    },
  ];
  const document: Level3D = {
    version: 1,
    map: "Derby",
    sceneAssets: [],
    size: [100, 100],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    provenance: {},
    groups: [{ id: "bridge", transform: { ...IDENTITY_TRANSFORM } }],
    objects: [
      {
        id: "mission-bridge",
        node: "mission-bridge",
        kind: "mission",
        group: "bridge",
        source: { map: "Derby", mission_profile: profile },
        obstacle: structuredClone(obstacle),
        transform: { ...IDENTITY_TRANSFORM },
      },
    ],
  };
  return { document, mission, nodes };
}

test("verified unchanged native preview is omitted only from static reconstruction", async () => {
  const f = fixture(),
    before = structuredClone(f.document);
  const out = await preserveNativePatchPreviews(f.document, { nodes: f.nodes }, async (name) => {
    assert.equal(name, "H03_Der_MK");
    return f.mission;
  });
  assert.equal(out.objects.length, 0);
  assert.deepEqual(f.document, before);
  assert.equal(out.provenance, f.document.provenance);
});

test("edited, hidden, duplicated, deleted and external previews fail closed", async () => {
  const changes: ((d: Level3D) => void)[] = [
    (d) => {
      d.objects[0]!.transform.dx = 1;
    },
    (d) => {
      d.groups[0]!.transform.rot_deg = 1;
    },
    (d) => {
      d.objects[0]!.hidden = true;
    },
    (d) => {
      d.groups[0]!.hidden = true;
    },
    (d) => {
      d.objects[0]!.obstacle.points[0]!.x = 2;
    },
    (d) => {
      d.objects.push({ ...d.objects[0]!, id: "duplicate" });
    },
    (d) => {
      d.objects = [];
    },
    (d) => {
      d.objects[0]!.source = { map: "Derby", mission_profile: "wrong" };
    },
    (d) => {
      d.objects[0]!.group = "missing";
    },
    (d) => {
      d.assetSources = [
        {
          id: "external",
          descriptor: "asset.json",
          model: "model.glb",
          descriptor_sha256: "a".repeat(64),
          model_sha256: "b".repeat(64),
        },
      ];
    },
  ];
  for (const change of changes) {
    const f = fixture();
    change(f.document);
    await assert.rejects(
      preserveNativePatchPreviews(f.document, { nodes: f.nodes }, async () => f.mission),
    );
  }
});

test("native mission bytes, profile and initial binding must match", async () => {
  const f = fixture();
  await assert.rejects(
    preserveNativePatchPreviews(f.document, { nodes: f.nodes }, async () => Buffer.from("changed")),
    /source changed/,
  );
  f.nodes[1]!.extras.native_patch_preview!.state = "applied";
  await assert.rejects(
    preserveNativePatchPreviews(f.document, { nodes: f.nodes }, async () => f.mission),
    /initial-patch binding/,
  );
});

test("even hash-matching native data must have the right map/profile and active initial graphic", async () => {
  for (const mutate of [
    (mission: any) => {
      mission.header.map_filename = "York";
    },
    (mission: any) => {
      mission.mission_patches[0].element_fx.sprite.profile_name = "Other bridge";
    },
    (mission: any) => {
      mission.mission_patches[0].element_fx.active = false;
    },
  ]) {
    const f = fixture();
    const mission = JSON.parse(f.mission.toString());
    mutate(mission);
    const bytes = Buffer.from(JSON.stringify(mission));
    f.nodes[1]!.extras.native_patch_preview!.mission_sha256 = sha(bytes);
    await assert.rejects(
      preserveNativePatchPreviews(f.document, { nodes: f.nodes }, async () => bytes),
      /profile\/map\/initial state mismatch/,
    );
  }
});
