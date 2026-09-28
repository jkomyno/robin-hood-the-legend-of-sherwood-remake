import test from "node:test";
import assert from "node:assert/strict";
import { joinedNavigationCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import type { ProtoLevel } from "../../shared/src/level.ts";
import {
  recoveredGameplayDefinition,
  type RecoveredGameplayPacket,
} from "./recovered-gameplay-definition.ts";
import {
  recoverReviewedNavigationJoins,
  type ReviewedNavigationJoins,
} from "./recover-reviewed-navigation-joins.ts";

function fixture() {
  const f = joinedNavigationCompilerFixture();
  const definitions: ReviewedNavigationJoins = {
    source_sha256: "source-pin",
    regions: [{ id: "roof", entries: [] }],
  };
  const packets = new Map<string, RecoveredGameplayPacket>();
  const source: Pick<ProtoLevel, "sight_obstacles" | "lifts"> = { sight_obstacles: [], lifts: [] };
  for (const [index, asset] of [f.hut, f.upper].entries()) {
    const surface = asset.gameplay!.surfaces[0]!;
    f.document.objects.find(
      (p) => p.node === `asset:${asset.id}:${surface.node}`,
    )!.source.obstacle = index;
    source.sight_obstacles.push({
      ...structuredClone(asset.parts[0]!.obstacle_local_game!),
      projection_area: [10, 2],
    });
    packets.set(asset.id, {
      asset: asset.id,
      surfaces: [
        {
          id: surface.id,
          node: surface.node,
          vertices: surface.polygon.map(([x, y], i) => [
            x,
            y,
            typeof surface.height === "number" ? surface.height : surface.height[i]!,
          ]),
          holes: [],
          kind: "walkable",
        },
      ],
      connections: [],
    });
    definitions.regions[0]!.entries.push({
      asset: asset.id,
      model_sha256: f.document.assetSources!.find((a) => a.id === asset.id)!.model_sha256,
      surface: surface.id,
      node: surface.node,
      source_obstacle: index,
      edges: structuredClone(surface.navigationJoins!),
    });
  }
  const recover = () =>
    recoverReviewedNavigationJoins(f.document, source, "source-pin", definitions, packets);
  return { ...f, definitions, packets, source, recover };
}

test("reviewed navigation recovery preserves local joins through packet conversion and compilation", () => {
  const f = fixture(),
    expected = compileAssetGameplay(f.document, f.assets, [0, 0, 2000, 2000]);
  const before = JSON.stringify([...f.packets]);
  const updates = f.recover();
  assert.equal(updates.length, 2);
  assert.equal(JSON.stringify([...f.packets]), before);
  for (const { surface, region, edges } of updates) {
    surface.navigationRegion = region;
    surface.navigationJoins = edges;
  }
  for (const [asset, packet] of f.packets) {
    const descriptor = f.assets.get(asset)!;
    const gameplay = recoveredGameplayDefinition(packet, descriptor);
    gameplay.collision = "none";
    f.assets.set(asset, { ...descriptor, gameplay });
  }
  assert.deepEqual(compileAssetGameplay(f.document, f.assets, [0, 0, 2000, 2000]), expected);
  f.definitions.regions[0]!.entries[0]!.edges[0]![0][0] += 5;
  assert.notDeepEqual(updates[0]!.edges, f.definitions.regions[0]!.entries[0]!.edges);
});

test("reviewed navigation rejects stale pins, wrong ownership and distinct source regions", () => {
  const f = fixture();
  f.definitions.source_sha256 = "changed";
  assert.throws(f.recover, /source changed/);
  f.definitions.source_sha256 = "source-pin";
  const entry = f.definitions.regions[0]!.entries[1]!,
    pin = entry.model_sha256;
  entry.model_sha256 = "changed";
  assert.throws(f.recover, /model changed/);
  entry.model_sha256 = pin;
  entry.source_obstacle = 0;
  assert.throws(f.recover, /source owner/);
  entry.source_obstacle = 1;
  f.source.sight_obstacles[1]!.projection_area = [11, 2];
  assert.throws(f.recover, /distinct source movement regions/);
});

test("reviewed navigation validates the entire catalog before updating any surfaces", () => {
  const f = fixture(),
    before = JSON.stringify([...f.packets]);
  f.definitions.regions[0]!.entries[1]!.edges[0]![0][2] += 1;
  assert.throws(f.recover, /outer surface edge/);
  assert.equal(JSON.stringify([...f.packets]), before);
  const detached = fixture();
  detached.document.groups.find((g) => g.id === "upper")!.transform.dx += 1;
  assert.throws(detached.recover, /detached edges/);
  const conflict = fixture();
  conflict.packets.get(conflict.hut.id)!.surfaces[0]!.navigationRegion = "another-room";
  assert.throws(conflict.recover, /conflicts with existing/);
  const repeated = fixture();
  repeated.definitions.regions[0]!.entries.push(
    structuredClone(repeated.definitions.regions[0]!.entries[0]!),
  );
  assert.throws(repeated.recover, /one ordinary surface/);
});
