import test from "node:test";
import assert from "node:assert/strict";
import { catalogFromExport } from "./prepare-publication-document.ts";
import type { AuthoredAssetCatalog } from "@rle/shared";
const catalog: AuthoredAssetCatalog = {
  map: "York",
  groups: [
    {
      id: "york-house",
      name: "House",
      parts: [
        { obstacle: 3, name: "Wall" },
        { node: "mission-door", name: "Door", mission_profile: "door" },
      ],
    },
  ],
};
const nodes = () => [
  { name: "map", children: [1, 4] },
  { name: "House", children: [2, 3], extras: { asset_group: "york-house" } },
  { name: "building-003", extras: { source_obstacle: 3, part_name: "Wall" } },
  {
    name: "mission-door",
    extras: {
      part_name: "Door",
      mission_patch_profile: "door",
      obstacle_local_game: { opaque: true, points: [] },
    },
  },
  { name: "ground" },
];
test("export authority includes supplemental parts and excludes terrain from selectable groups", () => {
  const result = catalogFromExport(nodes(), catalog);
  assert.equal(result.groups.length, 1);
  assert.equal(result.groups[0]!.parts.length, 2);
  assert.deepEqual(result.groups[0]!.parts[1]!.obstacle_local_game, { opaque: true, points: [] });
});
test("missing, duplicated and foreign ownership cannot initialize a document", () => {
  const missing = nodes();
  missing[1]!.children = [2];
  assert.throws(() => catalogFromExport(missing, catalog), /Missing reviewed group parts/);
  const duplicate = nodes();
  duplicate[1]!.children = [2, 2];
  assert.throws(() => catalogFromExport(duplicate, catalog), /duplicated/);
  const foreign = nodes();
  foreign[1]!.extras!.asset_group = "foreign";
  assert.throws(() => catalogFromExport(foreign, catalog), /reviewed catalog/);
  const wrong = nodes();
  wrong[2]!.extras!.source_obstacle = 9;
  assert.throws(() => catalogFromExport(wrong, catalog), /identity mismatch/);
});

test("split publication parts use scoped metadata rather than complete source obstacles", () => {
  const reviewed: AuthoredAssetCatalog = {
    map: "York",
    groups: [
      { id: "wall", name: "Wall", parts: [{ obstacle: 3, name: "West", components: ["west"] }] },
    ],
  };
  const footprint = { points: [{ x: 1, y: 2, z_bottom: 0, z_top: 3 }], opaque: true };
  const model = [
    { name: "map", children: [1] },
    { name: "Wall", children: [2], extras: { asset_group: "wall" } },
    {
      name: "building-003--component-west",
      extras: {
        source_obstacle: 3,
        part_name: "West",
        source_components: ["west"],
        obstacle_local_game: footprint,
      },
    },
  ];
  assert.equal(
    catalogFromExport(model, reviewed).groups[0]!.parts[0]!.obstacle_local_game,
    footprint,
  );
  model[2]!.extras!.source_components = ["east"];
  assert.throws(() => catalogFromExport(model, reviewed), /identity mismatch/);
});
