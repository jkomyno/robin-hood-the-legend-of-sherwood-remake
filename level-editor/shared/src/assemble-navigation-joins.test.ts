import test from "node:test";
import assert from "node:assert/strict";
import {
  assembleNavigationJoins,
  orientNavigationJoin,
  type PlacedNavigationJoin,
} from "./assemble-navigation-joins.ts";
import type { Vec3 } from "./scene.ts";

test("navigation sockets follow actual 3D boundary segments and projected winding", () => {
  const polygon: Vec3[] = [
    [0, 0, 0],
    [10, 0, 10],
    [10, 100, 10],
    [0, 100, 0],
  ];
  const edge: [Vec3, Vec3] = [
    [10, 80, 10],
    [10, 20, 10],
  ];
  assert.deepEqual(orientNavigationJoin(polygon, edge), [edge[1], edge[0]]);
  assert.deepEqual(orientNavigationJoin([...polygon].reverse(), edge), [edge[1], edge[0]]);
  assert.throws(
    () =>
      orientNavigationJoin(polygon, [
        [10, 20, 11],
        [10, 80, 11],
      ]),
    /outer surface edge/,
  );
  assert.throws(
    () =>
      orientNavigationJoin(polygon, [
        [5, 20, 5],
        [5, 80, 5],
      ]),
    /outer surface edge/,
  );
  assert.throws(
    () =>
      orientNavigationJoin(polygon, [
        [10, -1, 10],
        [10, 80, 10],
      ]),
    /outer surface edge/,
  );
  assert.throws(() => orientNavigationJoin(polygon, [edge[0], edge[0]]), /nondegenerate/);
});

test("navigation sockets reject ambiguous, overlapping and same-owner connections", () => {
  const a: PlacedNavigationJoin = {
    owner: "a",
    region: "a/roof",
    edge: [
      [10, 0, 5],
      [10, 100, 5],
    ],
  };
  const b: PlacedNavigationJoin = { owner: "b", region: "b/roof", edge: [a.edge[1], a.edge[0]] };
  const result = assembleNavigationJoins([a, b]);
  assert.equal(result.identities.get(a.region), result.identities.get(b.region));
  assert.deepEqual(result.unmatched, []);
  assert.equal(assembleNavigationJoins([a]).unmatched.length, 1);
  assert.throws(
    () => assembleNavigationJoins([a, b, { ...b, owner: "c", region: "c/roof" }]),
    /ambiguous/,
  );
  assert.throws(() => assembleNavigationJoins([a, { ...b, edge: a.edge }]), /overlapping/);
  assert.throws(() => assembleNavigationJoins([a, { ...b, owner: "a" }]), /ambiguous/);
  const raised = { ...b, edge: b.edge.map((p) => [p[0], p[1], p[2] + 1] as Vec3) as [Vec3, Vec3] };
  assert.equal(assembleNavigationJoins([a, raised]).unmatched.length, 2);
});

test("projected seams require both assets to explicitly allow their height step", () => {
  const a: PlacedNavigationJoin = {
    owner: "platform",
    region: "platform/walk",
    heightTolerance: 2,
    edge: [
      [10, 20, 20],
      [10, 40, 20],
    ],
  };
  const b: PlacedNavigationJoin = {
    owner: "bridge",
    region: "bridge/walk",
    heightTolerance: 2,
    edge: [
      [10, 41, 21],
      [10, 21.5, 21.5],
    ],
  };
  const joined = assembleNavigationJoins([a, b]);
  assert.equal(joined.identities.get(a.region), joined.identities.get(b.region));
  assert.equal(joined.unmatched.length, 0);
  assert.equal(
    assembleNavigationJoins([a, { ...b, heightTolerance: undefined }]).unmatched.length,
    2,
  );
  assert.equal(assembleNavigationJoins([a, { ...b, heightTolerance: 1 }]).unmatched.length, 2);
  const shifted = { ...b, edge: b.edge.map(([x, y, z]) => [x + 1, y, z] as Vec3) as [Vec3, Vec3] };
  assert.equal(assembleNavigationJoins([a, shifted]).unmatched.length, 2);
  assert.throws(
    () => assembleNavigationJoins([a, { ...b, edge: [b.edge[1], b.edge[0]] }]),
    /overlapping/,
  );
});
