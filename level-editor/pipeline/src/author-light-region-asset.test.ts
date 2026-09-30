import test from "node:test";
import assert from "node:assert/strict";
import { NodeIO } from "@gltf-transform/core";
import { authorLightRegionAsset } from "./author-light-region-asset.ts";
import { declaredLightOwners } from "./recover-light-owner.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import type { LightSector } from "../../shared/src/level.ts";

const light: LightSector = {
  layer: 0,
  ambience: 4,
  polygon: {
    points: [
      [310, 310],
      [330, 310],
      [330, 330],
      [310, 330],
    ],
  },
};
const options = {
  id: "night-region",
  name: "Night region",
  map: "test",
  origin: [310, 310, 0] as [number, number, number],
};

test("authored light regions preserve contours and ambience and move independently", async () => {
  const { descriptor, model, placement } = await authorLightRegionAsset(
    light,
    [],
    [
      {
        polygon: light.polygon,
        is_lift: false,
        state_id: 0,
        flags: 0,
        skeleton_segments: [],
        obstacles: [],
      },
    ],
    options,
  );
  assert.equal((await new NodeIO().readBinary(model)).getRoot().listMeshes().length, 0);
  assert.equal(descriptor.parts[0]!.gameplay_only, true);
  const { document, assets } = assetCompilerFixture();
  document.objects.push(placement);
  assets.set(descriptor.id, descriptor);
  const bounds: [number, number, number, number] = [0, 0, 2000, 2000];
  const baseline = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(baseline.light_sectors, [light]);
  placement.transform.dx += 100;
  const moved = compileAssetGameplay(document, assets, bounds);
  assert.deepEqual(moved.light_sectors, [
    { ...light, polygon: { points: light.polygon.points.map(([x, y]) => [x + 100, y]) } },
  ]);
  const { light_sectors: beforeLights, ...before } = baseline;
  const { light_sectors: afterLights, ...after } = moved;
  assert.ok(beforeLights && afterLights);
  assert.deepEqual(after, before);
  document.objects.push({ ...structuredClone(placement), id: "copy" });
  assert.equal(compileAssetGameplay(document, assets, bounds).light_sectors!.length, 2);
  await assert.rejects(
    authorLightRegionAsset(light, [], [], { ...options, origin: [NaN, 0, 0] }),
    /origin must be finite/,
  );
});

test("light declarations reject changed sources and ambiguous ownership", () => {
  const frame = { id: "frame" };
  const entry = {
    source: 0,
    owner: options.id,
    node: "scenery-light",
    reason: "Independent camp field",
    light,
  };
  assert.equal(declaredLightOwners([entry], [light], () => [frame]).get(0)!.part, frame);
  assert.throws(() => declaredLightOwners([entry, entry], [light], () => [frame]), /one source/);
  assert.throws(
    () => declaredLightOwners([{ ...entry, reason: " " }], [light], () => [frame]),
    /reviewed asset frame/,
  );
  assert.throws(
    () => declaredLightOwners([entry], [{ ...light, ambience: 1 }], () => [frame]),
    /source changed/,
  );
  assert.throws(() => declaredLightOwners([entry], [light], () => []), /one pinned frame/);
  assert.throws(
    () => declaredLightOwners([entry], [light], () => [frame, frame]),
    /one pinned frame/,
  );
});
