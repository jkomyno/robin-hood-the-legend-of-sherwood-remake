import test from "node:test";
import assert from "node:assert/strict";
import derby from "../assets/derby.json" with { type: "json" };
import {
  appendSupplementalMissionParts,
  authoredAssetGroups,
  catalogForLegacyReconstruction,
  upgradeGeneratedAssetGroups,
  type AuthoredAssetCatalog,
} from "./authored-assets.ts";
import { IDENTITY_TRANSFORM, type Level3D, type Level3DObject } from "./level3d.ts";

// Keep the legacy canonical fixture explicit when the shipped catalog adds
// supplemental mission previews that older generated GLBs do not contain.
const embeddedCatalog: AuthoredAssetCatalog = derby;
const legacyCatalog: AuthoredAssetCatalog = {
  ...embeddedCatalog,
  groups: embeddedCatalog.groups.flatMap((group) => {
    const parts = group.parts.filter((part) => part.obstacle !== undefined);
    return parts.length ? [{ ...group, parts }] : [];
  }),
};

function objects(): Level3DObject[] {
  return Array.from({ length: 271 }, (_, obstacle) => obstacle)
    .filter((obstacle) => obstacle !== 35)
    .map((obstacle) => ({
      id: `building-${String(obstacle).padStart(3, "0")}`,
      node: `building-${String(obstacle).padStart(3, "0")}`,
      kind: "building",
      source: { map: "Derby", obstacle },
      obstacle: {
        points: [],
        opaque: true,
        solid: true,
        mouse: false,
        show_shadow_polygon: false,
        default_material: 0,
        material_indices: [],
        projection_area: {},
      },
      transform: { ...IDENTITY_TRANSFORM },
    }));
}

test("Derby assigns every exported obstacle to exactly one named logical asset", () => {
  const parts = objects();
  const before = structuredClone(parts);
  const groups = authoredAssetGroups("Derby", parts)!;
  const members = legacyCatalog.groups.flatMap((group) => group.parts.map((part) => part.obstacle));
  assert.equal(members.length, 270);
  assert.equal(new Set(members).size, 270);
  assert.equal(groups.length, 39);
  assert.equal(new Set(groups.map((group) => group.id)).size, groups.length);
  assert.ok(groups.every((group) => group.name && !group.name.startsWith("group-")));
  for (const [i, part] of parts.entries()) {
    assert.ok(groups.some((group) => group.id === part.group));
    assert.ok(part.name);
    const { name: _name, group: _group, ...unchanged } = part;
    assert.deepEqual(unchanged, before[i]);
  }
  const owner = (id: number) => parts.find((part) => part.source.obstacle === id)!.group;
  assert.equal(owner(49), owner(50)); // Both sides of the east cottage.
  assert.equal(owner(130), owner(239)); // West tower retains its revealed landing.
  assert.equal(owner(143), owner(227)); // Keep hall retains its fireplace interior.
  assert.equal(owner(163), owner(173)); // North tower retains its roof.
  assert.equal(owner(152), owner(161)); // Central turret retains its gallery.
  assert.equal(new Set([130, 143, 163, 152].map(owner)).size, 4);
  assert.equal(owner(27), owner(32)); // Wall turret retains every roof sector.
  assert.equal(owner(36), owner(38)); // Access stairs stay with their landing.
  assert.equal(owner(23), owner(45)); // Wall runs retain the continuous walk.
  assert.equal(new Set([27, 36, 23].map(owner)).size, 3);
  assert.equal(owner(183), owner(210)); // East hall and its roof turret.
  assert.equal(owner(7), owner(12)); // Curtain wall and access stair.
  assert.notEqual(owner(183), owner(214)); // Hall and freestanding watchtower.
  assert.notEqual(owner(49), owner(55)); // Neighboring houses stay independent.
});

test("catalog mismatch fails before mutating a document; other maps retain inferred grouping", () => {
  const parts = objects().slice(1);
  const before = structuredClone(parts);
  assert.throws(() => authoredAssetGroups("Derby", parts), /obstacle set/);
  assert.deepEqual(parts, before);
  assert.equal(authoredAssetGroups("York", parts), null);
  assert.deepEqual(parts, before);
});

test("untouched saved groups upgrade once, but saved transforms and custom ownership survive", () => {
  const document: Level3D = {
    version: 1,
    map: "Derby",
    sceneAssets: [],
    size: [1920, 2752],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    objects: objects(),
    groups: [{ id: "group-000", transform: { ...IDENTITY_TRANSFORM } }],
  };
  for (const part of document.objects) part.group = "group-000";
  const edited = structuredClone(document);
  edited.groups[0].transform.dx = 10;
  const snapshot = structuredClone(edited);
  assert.equal(upgradeGeneratedAssetGroups(edited), false);
  assert.deepEqual(edited, snapshot);
  assert.equal(upgradeGeneratedAssetGroups(document), true);
  assert.equal(document.groups.length, 39);
  assert.equal(upgradeGeneratedAssetGroups(document), false);
});

test("explicit catalogs support another map and reject ambiguous ownership atomically", () => {
  const parts = objects()
    .slice(0, 2)
    .map((part) => ({ ...part, source: { ...part.source, map: "Leicester" } }));
  const catalog = {
    map: "Leicester",
    groups: [
      {
        id: "leicester-house",
        name: "Leicester House",
        parts: [
          { obstacle: 0, name: "Walls" },
          { obstacle: 1, name: "Roof" },
        ],
      },
    ],
  };
  const before = structuredClone(parts);
  assert.throws(
    () =>
      authoredAssetGroups("Leicester", parts, {
        ...catalog,
        groups: [catalog.groups[0], catalog.groups[0]],
      }),
    /duplicate group/,
  );
  assert.deepEqual(parts, before);
  const duplicatePart = structuredClone(catalog);
  duplicatePart.groups[0].parts.push({ obstacle: 0, name: "Second owner" });
  assert.throws(() => authoredAssetGroups("Leicester", parts, duplicatePart), /duplicate obstacle/);
  assert.deepEqual(parts, before);
  assert.throws(() => authoredAssetGroups("York", parts, catalog), /different map/);
  const groups = authoredAssetGroups("leicester", parts, catalog)!;
  assert.equal(groups[0].name, "Leicester House");
  assert.deepEqual(
    parts.map((part) => [part.group, part.name]),
    [
      ["leicester-house", "Walls"],
      ["leicester-house", "Roof"],
    ],
  );
});

test("exported catalogs upgrade pristine non-Derby documents without replacing edits", () => {
  const parts = objects()
    .slice(0, 2)
    .map((part) => ({ ...part, group: "group-000", source: { ...part.source, map: "Leicester" } }));
  const catalog = {
    map: "Leicester",
    groups: [
      {
        id: "house",
        name: "House",
        parts: [
          { obstacle: 0, name: "Body" },
          { obstacle: 1, name: "Roof" },
        ],
      },
    ],
  };
  const document: Level3D = {
    version: 1,
    map: "Leicester",
    sceneAssets: [],
    size: [100, 100],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    objects: parts,
    groups: [{ id: "group-000", transform: { ...IDENTITY_TRANSFORM } }],
  };
  const edited = structuredClone(document);
  edited.objects[0].name = "My edited wall";
  const before = structuredClone(edited);
  assert.equal(upgradeGeneratedAssetGroups(edited, catalog), false);
  assert.deepEqual(edited, before);
  assert.equal(upgradeGeneratedAssetGroups(document, catalog), true);
  assert.equal(document.groups[0].id, "house");
  assert.equal(upgradeGeneratedAssetGroups(document, catalog), false);
});

test("explicit mission publication adds one group/part while preserving all 270 existing parts", () => {
  const parts = objects();
  for (const part of parts)
    part.obstacle.points = [
      { x: 0, y: 0, z_bottom: 0, z_top: 5 },
      { x: 10, y: 0, z_bottom: 0, z_top: 5 },
      { x: 0, y: 10, z_bottom: 0, z_top: 5 },
    ];
  const document: Level3D = {
    version: 1,
    map: "Derby",
    sceneAssets: [],
    size: [1920, 2752],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    objects: parts,
    groups: authoredAssetGroups("Derby", parts)!,
  };
  document.objects[0].transform.dx = 17;
  document.objects[1].hidden = true;
  const before = structuredClone(document);
  const supplemental = {
    node: "mission-second-drawbridge",
    name: "Raised bridge",
    mission_profile: "Derby - Pont_levis02",
    obstacle_local_game: structuredClone(parts[0].obstacle),
  };
  const group = {
    id: "derby-second-drawbridge",
    name: "Second courtyard drawbridge",
    parts: [supplemental],
  };
  const catalog: AuthoredAssetCatalog = { map: "Derby", groups: [...legacyCatalog.groups, group] };
  const next = appendSupplementalMissionParts(document, catalog, [supplemental.node]);
  assert.equal(next.objects.length, 271);
  assert.equal(next.groups.length, 40);
  assert.deepEqual(next.objects.slice(0, 270), before.objects);
  assert.deepEqual(next.groups.slice(0, 39), before.groups);
  assert.deepEqual(document, before);
  assert.deepEqual(next.objects[270].source, {
    map: "Derby",
    mission_profile: supplemental.mission_profile,
  });
  assert.equal(authoredAssetGroups("Derby", structuredClone(next.objects), catalog)!.length, 40);
  assert.throws(
    () => appendSupplementalMissionParts(next, catalog, [supplemental.node]),
    /already exists/,
  );
  assert.throws(
    () => appendSupplementalMissionParts(document, catalog, ["mission-absent"]),
    /does not match/,
  );
  assert.throws(
    () => appendSupplementalMissionParts(document, catalog, ["building-267"]),
    /allowlist/,
  );
  assert.throws(
    () =>
      appendSupplementalMissionParts(document, { ...catalog, groups: [...catalog.groups, group] }, [
        supplemental.node,
      ]),
    /duplicate/,
  );
});

test("legacy fallback skips absent explicit mission previews but never missing canonical parts", () => {
  const supplemental = {
    node: "mission-second-drawbridge",
    name: "Drawbridge endpoint",
    mission_profile: "Derby - Pont_levis02",
  };
  const catalog: AuthoredAssetCatalog = {
    ...legacyCatalog,
    groups: [
      ...legacyCatalog.groups,
      { id: "derby-second-drawbridge", name: "Second Courtyard Drawbridge", parts: [supplemental] },
    ],
  };
  const old = objects();
  const fallback = catalogForLegacyReconstruction(catalog, old);
  assert.equal(fallback.groups.length, 39);
  assert.equal(authoredAssetGroups("Derby", old, fallback)!.length, 39);
  assert.throws(() => authoredAssetGroups("Derby", objects(), catalog), /obstacle set/);
  const missing = objects().slice(1);
  assert.throws(
    () => authoredAssetGroups("Derby", missing, catalogForLegacyReconstruction(catalog, missing)),
    /obstacle set/,
  );
  const mission: Level3DObject = {
    ...objects()[0],
    id: supplemental.node,
    node: supplemental.node,
    kind: "mission",
    source: { map: "Derby", mission_profile: supplemental.mission_profile },
  };
  const current = [...objects(), mission];
  assert.equal(catalogForLegacyReconstruction(catalog, current).groups.length, 40);
  assert.equal(authoredAssetGroups("Derby", current, catalog)!.length, 40);
});

test("scoped components of one obstacle retain independent reviewed groups", () => {
  const catalog: AuthoredAssetCatalog = {
    map: "Derby",
    groups: ["west", "east"].map((component) => ({
      id: component,
      name: component,
      parts: [{ obstacle: 0, components: [component], name: "Wall" }],
    })),
  };
  const parts = ["west", "east"].map((component) => ({
    ...objects()[0],
    node: `building-000--component-${component}`,
    id: component,
    source: { map: "Derby", obstacle: 0, components: [component] },
  }));
  authoredAssetGroups("Derby", parts, catalog);
  assert.deepEqual(
    parts.map((part) => part.group),
    ["west", "east"],
  );
  const overlap = structuredClone(catalog);
  overlap.groups[1].parts[0] = { obstacle: 0, name: "Whole wall" };
  assert.throws(() => authoredAssetGroups("Derby", parts, overlap), /overlapping/);
  parts[1].source.components = ["west"];
  assert.throws(() => authoredAssetGroups("Derby", parts, catalog), /obstacle set/);
});
