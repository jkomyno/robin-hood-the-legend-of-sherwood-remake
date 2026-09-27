import test from "node:test";
import assert from "node:assert/strict";
import type { SightObstacle } from "@rle/shared";
import {
  declaredEndpointBindings,
  recoverDeclaredEndpoint,
  type EndpointBindingDeclaration,
} from "./recovery-endpoint-binding.ts";

const binding: EndpointBindingDeclaration = {
  kind: "door-inside",
  index: 2,
  projection: 0,
  anchor: [30, 5],
  reason: "The traversal endpoint is on the adjoining support, before the receiving landing.",
};
const support: SightObstacle = {
  points: [
    [0, 0],
    [10, 0],
    [10, 10],
    [0, 10],
  ].map(([x, y]) => ({
    x: x!,
    y: y! + 20,
    z_bottom: 0,
    z_top: 20,
  })),
  projection_area: [4, 2],
  opaque: true,
  solid: true,
  mouse: true,
  show_shadow_polygon: false,
  default_material: 0,
  material_indices: [],
};

test("explicit endpoint bindings separate physical height from receiving area", () => {
  const recovered = recoverDeclaredEndpoint(
    binding,
    [5, 5],
    2,
    [support],
    (point) => {
      assert.deepEqual(point, [30, 5]);
      return 40;
    },
    (shape, point) => {
      assert.equal(shape, support);
      assert.deepEqual(point, [5, 5]);
      return 20;
    },
  );
  assert.deepEqual(recovered, { height: 20, anchor: [30, 45, 40] });
  assert.ok(!JSON.stringify(recovered).includes("projection"));
});

test("declarations require unique valid identities and authoring evidence", () => {
  assert.equal(declaredEndpointBindings([binding], 3, 1).get("door-inside/2"), binding);
  for (const invalid of [
    { ...binding, index: 3 },
    { ...binding, projection: -1 },
    { ...binding, reason: "" },
    { ...binding, anchor: [NaN, 5] as [number, number] },
    { ...binding, kind: "patch-waypoint" as const, index: 1 },
  ])
    assert.throws(() => declaredEndpointBindings([invalid], 3, 1), /Invalid/);
  assert.throws(() => declaredEndpointBindings([binding, binding], 3, 1), /duplicate/);
});

test("physical projection must contain the endpoint on the authored layer", () => {
  const recover = (point: [number, number], layer: number, obstacles: SightObstacle[]) =>
    recoverDeclaredEndpoint(
      binding,
      point,
      layer,
      obstacles,
      () => 40,
      () => 20,
    );
  assert.throws(() => recover([15, 5], 2, [support]), /must contain/);
  assert.throws(() => recover([5, 5], 3, [support]), /must contain/);
  assert.throws(() => recover([5, 5], 2, []), /must contain/);
  assert.throws(() => recover([5, 5], 2, [{ ...support, projection_area: {} }]), /must contain/);
  assert.throws(
    () =>
      recoverDeclaredEndpoint(
        binding,
        [5, 5],
        2,
        [support],
        () => {
          throw new Error("Receiver not found");
        },
        () => 20,
      ),
    /Receiver not found/,
  );
});
