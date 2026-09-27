import test from "node:test";
import assert from "node:assert/strict";
import { sightTransitionCompilerFixture } from "../test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "./compile-asset-gameplay.ts";
import { normalizeGameplayStateViews } from "./gameplay-state-views.ts";
import { assetVariantId } from "./projection-assets.ts";
import { partMatrix } from "./level3d.ts";

const bounds: [number, number, number, number] = [0, 0, 2000, 2000];
function fixture() {
  const f = sightTransitionCompilerFixture();
  const { hut, document, assets } = f;
  const initial = hut.parts[0]!;
  const volume = hut.gameplay!.volumes![0]!;
  const applied = {
    name: initial.name,
    node: "open",
    source_obstacle: 1000,
    obstacle_local_game: { ...volume.shape, projection_area: null, material_indices: [] },
  };
  delete hut.gameplay!.volumes;
  hut.gameplay!.movementTransitions![0]!.appliedSight = ["open"];
  hut.parts.push(applied);
  const body = document.objects.find((part) => part.node === "asset:hut:building-999")!;
  const open = {
    ...body,
    id: "open",
    node: "asset:hut:open",
    obstacle: applied.obstacle_local_game,
  };
  document.objects.push(open);
  const expected = compileAssetGameplay(document, assets, bounds);
  hut.parts = [initial];
  hut.state_variants = {
    initial: { name: "Initial", model: hut.model, parts: [initial] },
    applied: { name: "Applied", model: hut.model, parts: [initial, applied] },
  };
  const alias = assetVariantId(hut.id, "applied");
  assets.set(alias, { ...hut, id: alias, parts: [initial, applied] });
  document.assetSources!.push({
    ...document.assetSources![0]!,
    id: alias,
    state_variant: "applied",
  });
  open.node = `asset:${alias}:open`;
  return { ...f, expected, alias, body };
}

test("state views compile as one gameplay instance without changing the saved document", () => {
  const { document, assets, expected } = fixture();
  const before = structuredClone(document);
  assert.deepEqual(compileAssetGameplay(document, assets, bounds), expected);
  assert.deepEqual(document, before);
});

test("initial-only insertion creates hidden gameplay frames for alternate parts", () => {
  const { document, assets, expected, alias } = fixture();
  document.objects = document.objects.filter((part) => !part.node.startsWith(`asset:${alias}:`));
  assert.deepEqual(compileAssetGameplay(document, assets, bounds), expected);
});

test("adding alternate frames preserves rotated and elevated placement matrices", () => {
  const { document, assets, alias, body } = fixture();
  document.objects = document.objects.filter((part) => !part.node.startsWith(`asset:${alias}:`));
  const group = document.groups.find((g) => g.id === body.group)!;
  group.transform = { dx: 500, dy: 300, dz: 35, rot_deg: 37 };
  body.transform.rot_deg = 19;
  body.transform.dz = 12;
  const expected = partMatrix(document.camera, document, body);
  const before = structuredClone(document);
  const normalized = normalizeGameplayStateViews(document, assets);
  for (const part of normalized.document.objects.filter((p) => p.group === body.group)) {
    const actual = partMatrix(document.camera, normalized.document, part);
    actual.forEach((value, i) => assert.ok(Math.abs(value - expected[i]!) < 1e-9));
  }
  const twice = normalizeGameplayStateViews(normalized.document, normalized.descriptors);
  assert.deepEqual(twice, normalized);
  assert.deepEqual(document, before);
});

test("missing state frames reject independently edited placement parts", () => {
  const { document, assets, alias, body, hut } = fixture();
  document.objects = document.objects.filter((part) => !part.node.startsWith(`asset:${alias}:`));
  const extra = { ...structuredClone(hut.parts[0]!), node: "extra" };
  hut.parts.push(extra);
  document.objects.push({
    ...structuredClone(body),
    id: "extra",
    node: "asset:hut:extra",
    transform: { ...body.transform, dx: body.transform.dx + 5 },
  });
  assert.throws(() => normalizeGameplayStateViews(document, assets), /independently edited/);
});

test("shared parts deduplicate in either order but conflicting frames fail", () => {
  const { document, assets, alias, body } = fixture();
  const duplicate = {
    ...structuredClone(body),
    id: "shared-view",
    node: `asset:${alias}:building-999`,
  };
  document.objects.unshift(duplicate);
  document.groups.find((group) => group.id === body.group)!.transform.rot_deg = 31;
  const expected = partMatrix(document.camera, document, body);
  const normalized = normalizeGameplayStateViews(document, assets);
  assert.equal(normalized.document.objects.filter((p) => p.node === body.node).length, 1);
  const actual = partMatrix(document.camera, normalized.document, body);
  actual.forEach((value, i) => assert.ok(Math.abs(value - expected[i]!) < 1e-9));
  duplicate.transform.dx += 1;
  assert.throws(() => normalizeGameplayStateViews(document, assets), /disagree/);
});

test("duplicated stateful assets get independent transformed gameplay", () => {
  const { document, assets, body } = fixture();
  const group = document.groups.find((g) => g.id === body.group)!;
  document.groups.push({
    ...structuredClone(group),
    id: "copy",
    transform: { ...group.transform, dx: group.transform.dx + 300 },
  });
  document.objects.push(
    ...document.objects
      .filter((part) => part.group === group.id)
      .map((part) => ({ ...structuredClone(part), id: `${part.id}-copy`, group: "copy" })),
  );
  const compiled = compileAssetGameplay(document, assets, bounds);
  assert.equal(compiled.movement_transitions!.length, 2);
  const [a, b] = compiled.movement_transitions!;
  assert.notDeepEqual(a!.initial_sight, b!.initial_sight);
  assert.notDeepEqual(a!.applied_sight, b!.applied_sight);
  assert.notDeepEqual(a!.waypoint, b!.waypoint);
});

test("state families reject mismatched pins and reused changing part identities", () => {
  const { document, assets, hut, alias } = fixture();
  const reference = document.assetSources!.find((source) => source.id === alias)!;
  reference.descriptor_sha256 = "1".repeat(64);
  assert.throws(() => normalizeGameplayStateViews(document, assets), /pinned primary/);
  reference.descriptor_sha256 = document.assetSources![0]!.descriptor_sha256;
  const part = structuredClone(hut.parts[0]!);
  part.obstacle_local_game!.points[0]!.x += 1;
  hut.state_variants!.applied!.parts = [part];
  assert.throws(() => normalizeGameplayStateViews(document, assets), /distinct local state part/);
});

test("profile-backed editor bounds do not become alternate map collision", () => {
  const { document, assets, hut } = fixture();
  const initial = hut.parts[0]!;
  const placeholder = {
    node: "profile",
    name: "Profile bounds",
    mission_profile: "fixture",
    obstacle_local_game: structuredClone(initial.obstacle_local_game!),
  };
  const alternate = structuredClone(placeholder);
  alternate.obstacle_local_game.points[0]!.x += 20;
  hut.parts.push(placeholder);
  hut.state_variants!.applied!.parts!.push(alternate);
  const normalized = normalizeGameplayStateViews(document, assets);
  assert.deepEqual(
    normalized.descriptors.get(hut.id)!.parts.find((part) => part.node === "profile"),
    placeholder,
  );
});
