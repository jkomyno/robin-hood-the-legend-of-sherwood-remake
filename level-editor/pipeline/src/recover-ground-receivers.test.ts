import test from "node:test";
import assert from "node:assert/strict";
import { anchoredReceiverCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import {
  recoverGroundReceivers,
  type ReviewedGroundReceivers,
} from "./recover-ground-receivers.ts";

function fixture() {
  const { document, assets, hut } = anchoredReceiverCompilerFixture();
  document.objects[0]!.source.obstacle = 0;
  const source = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const definitions: ReviewedGroundReceivers = {
    source_sha256: "source-pin",
    entries: [
      {
        asset: hut.id,
        node: hut.parts[0]!.node,
        model_sha256: "0".repeat(64),
        source_obstacle: 0,
        anchor: [350, 350],
      },
    ],
  };
  const recover = () =>
    recoverGroundReceivers(
      document,
      assets,
      source,
      "source-pin",
      definitions,
      (_part, [x, y, z]) => [x - 300, y - 300, z],
    );
  return { document, assets, source, definitions, recover };
}

test("ground receiver recovery validates physical ownership and localizes the navigation anchor", () => {
  const { recover } = fixture();
  assert.deepEqual(recover()[0]!.localAnchor, [50, 50, 0]);
});

test("ground receiver recovery rejects stale geometry, ownership and blocked navigation", () => {
  const changes: ((f: ReturnType<typeof fixture>) => void)[] = [
    (f) => {
      f.definitions.source_sha256 = "stale";
    },
    (f) => {
      f.definitions.entries[0]!.model_sha256 = "stale";
    },
    (f) => {
      f.source.sight_obstacles[0]!.points[0]!.x += 1;
    },
    (f) => {
      f.document.objects.push(structuredClone(f.document.objects[0]!));
    },
    (f) => {
      f.definitions.entries.push(structuredClone(f.definitions.entries[0]!));
    },
    (f) => {
      f.definitions.entries[0]!.anchor = [900, 900];
    },
    (f) => {
      f.source.motion_data.layers[0]![0]!.state_id = 1;
    },
    (f) => {
      f.source.sight_obstacles[0]!.projection_area = [0, 1];
    },
    (f) => {
      f.source.motion_data.layers[0]![0]!.obstacles.push({
        state_id: 0,
        polygon: {
          points: [
            [340, 340],
            [360, 340],
            [360, 360],
            [340, 360],
          ],
        },
      });
    },
  ];
  for (const change of changes) {
    const f = fixture();
    change(f);
    assert.throws(f.recover, /Ground receiver/);
  }
});
