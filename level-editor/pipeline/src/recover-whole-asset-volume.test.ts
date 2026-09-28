import assert from "node:assert/strict";
import test from "node:test";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { IDENTITY_TRANSFORM } from "../../shared/src/level3d.ts";
import { recoverWholeAssetVolume } from "./recover-whole-asset-volume.ts";
import { recoveredGameplayDefinition } from "./recovered-gameplay-definition.ts";

function fixture() {
  const fixture = assetCompilerFixture();
  const descriptor = fixture.hut;
  const part = descriptor.parts[0]!;
  part.source_obstacle = 650;
  const source = structuredClone(part.obstacle_local_game!);
  source.projection_area = null;
  source.material_indices = [];
  source.solid = false;
  descriptor.parts.push({ ...structuredClone(part), node: "second-component" });
  return {
    ...fixture,
    options: {
      descriptor,
      source,
      sourceIndex: 650,
      node: part.node,
      localize: (point: [number, number, number]) => point,
    },
  };
}

test("whole physical volume survives conversion and follows asset placement", () => {
  const { options, hut, document, assets } = fixture();
  const original = structuredClone(options.source);
  const recovered = recoverWholeAssetVolume(options);
  const surfaces = hut.gameplay!.surfaces;
  hut.gameplay = recoveredGameplayDefinition(
    { asset: hut.id, surfaces: [], connections: [], ...recovered },
    hut,
  );
  hut.gameplay.surfaces = surfaces;
  assert.equal(hut.gameplay.collision, "none");
  const bounds: [number, number, number, number] = [0, 0, 2000, 2000];
  const before = compileAssetGameplay(document, assets, bounds);
  assert.equal(before.sight_obstacles.length, 1);
  assert.equal(before.sight_obstacles[0]!.solid, false);
  document.groups[0]!.transform.dx += 100;
  const after = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(
    after.sight_obstacles[0]!.points,
    before.sight_obstacles[0]!.points.map((p) => ({ ...p, x: p.x + 100 })),
  );
  assert.deepEqual(options.source, original);
  const copy = structuredClone(document.objects[0]!);
  copy.id = "volume-copy";
  copy.group = "volume-copy";
  copy.transform = { ...IDENTITY_TRANSFORM };
  document.objects.push(copy);
  document.groups.push({
    id: "volume-copy",
    transform: { ...IDENTITY_TRANSFORM, dx: 1100, dy: 400, rot_deg: 90 },
  });
  const duplicated = compileAssetGameplay(document, assets, bounds);
  assert.equal(duplicated.sight_obstacles.length, 2);
  assert.deepEqual(duplicated.sight_obstacles[0], after.sight_obstacles[0]);
  assert.notDeepEqual(duplicated.sight_obstacles[1]!.points, after.sight_obstacles[0]!.points);
  assert.equal(duplicated.sight_obstacles[1]!.solid, false);
  recovered.volumes[0].shape.points[0]!.z_top += 10;
  assert.notDeepEqual(hut.gameplay.volumes, recovered.volumes);
});

test("localization retains ordered bottom/top planes and flags", () => {
  const { options } = fixture();
  options.localize = ([x, y, z]) => [x - 13, y + 7, z - 4];
  const shape = recoverWholeAssetVolume(options).volumes[0].shape;
  assert.deepEqual(
    shape.points,
    options.source.points.map((p) => ({
      x: p.x - 13,
      y: p.y + 7,
      z_bottom: p.z_bottom - 4,
      z_top: p.z_top - 4,
    })),
  );
  assert.equal(shape.opaque, options.source.opaque);
  assert.equal(shape.show_shadow_polygon, options.source.show_shadow_polygon);
});

test("whole-volume recovery refuses ambiguous ownership or receiving metadata", () => {
  for (const mutate of [
    (o: ReturnType<typeof fixture>["options"]) => {
      o.descriptor.parts[1]!.source_obstacle = 651;
    },
    (o: ReturnType<typeof fixture>["options"]) => {
      o.node = "missing";
    },
    (o: ReturnType<typeof fixture>["options"]) => {
      o.descriptor.parts[1]!.mission_profile = "preview";
    },
  ]) {
    const { options } = fixture();
    mutate(options);
    assert.throws(() => recoverWholeAssetVolume(options), /exclusive ownership/);
  }
  const { options } = fixture();
  options.source.projection_area = [0, 0];
  assert.throws(() => recoverWholeAssetVolume(options), /separate authoring/);
  options.source.projection_area = null;
  options.source.material_indices = [1];
  assert.throws(() => recoverWholeAssetVolume(options), /separate authoring/);
  options.source.material_indices = [];
  options.localize = ([x, y, z]) => [x + z, y, z];
  assert.throws(() => recoverWholeAssetVolume(options), /vertical asset frame/);
});
