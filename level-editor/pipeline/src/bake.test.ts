import assert from "node:assert/strict";
import test from "node:test";
import { assertReconstructedBakeSources } from "./bake.ts";

test("supplemental mission models cannot be baked as indexed obstacles", () => {
  assert.throws(() => assertReconstructedBakeSources({ objects: [{ kind: "mission", source: { mission_profile: "Derby - Pont_levis02" } }] }), /supplemental mission/);
});

test("reconstruction bake rejects external meshes even when instances are hidden", () => {
  assert.throws(
    () => assertReconstructedBakeSources({
      assetSources: [{ id: "well", model: "assets/well/model.glb" }],
      objects: [{ hidden: true }],
    }),
    /does not yet support imported standalone assets/,
  );
});

test("existing reconstructed documents and absent optional documents remain supported", () => {
  assert.doesNotThrow(() => assertReconstructedBakeSources(undefined));
  assert.doesNotThrow(() => assertReconstructedBakeSources({ objects: [] }));
  assert.doesNotThrow(() => assertReconstructedBakeSources({ assetSources: [] }));
});

test("spline geometry cannot silently disappear during game baking", () => {
  assert.throws(() => assertReconstructedBakeSources({ splines: [{ kind: "river" }] }), /spline geometry/);
});

test("split source components cannot silently replace complete canonical obstacles", () => {
  assert.throws(() => assertReconstructedBakeSources({objects:[{source:{obstacle:0,components:["west"]}}]}), /split obstacle/);
  assert.throws(() => assertReconstructedBakeSources({objects:[{node:"building-000--component-west"}]}), /split obstacle/);
});
