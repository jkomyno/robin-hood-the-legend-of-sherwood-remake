import test from "node:test";
import assert from "node:assert/strict";
import { nonrenderingGameplayOwners } from "./nonrendering-gameplay-owners.ts";

test("explicit invisible gameplay ownership resolves against pinned asset frames", () => {
  const catalog = {
    groups: [{ id: "house", parts: [{ obstacle: 1 }, { obstacle: 2 }] }],
    nonrendering_sources: [{ obstacle: 3, owner: "house" }],
  };
  const owners = new Map([
    [1, [{ asset: "legacy-house", node: "body" }]],
    [2, [{ asset: "legacy-house", node: "roof" }]],
  ]);
  assert.equal(nonrenderingGameplayOwners(catalog, owners)[0]!.owner!.node, "body");
  owners.set(2, [{ asset: "another-house", node: "roof" }]);
  assert.equal(nonrenderingGameplayOwners(catalog, owners)[0]!.owner, undefined);
  owners.set(1, [{ asset: "house", node: "body" }]);
  assert.equal(nonrenderingGameplayOwners(catalog, owners)[0]!.owner!.asset, "house");
  assert.throws(
    () => nonrenderingGameplayOwners({ ...catalog, groups: [] }, owners),
    /Missing gameplay ownership/,
  );
});
