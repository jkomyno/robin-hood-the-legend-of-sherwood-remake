import test from "node:test";
import assert from "node:assert/strict";
import { IDENTITY_TRANSFORM } from "@rle/shared";
import { compileAssetGameplay } from "../../shared/src/compile-asset-gameplay.ts";
import { movementTransitionCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { navigationStateAsset } from "./navigation-state-asset.ts";

test("navigation-only assets carry local state geometry through movement and duplication", () => {
  const { document, assets, hut } = movementTransitionCompilerFixture();
  const before = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  const obstacles = before.motion_data.layers.flatMap((layer) =>
    layer.flatMap((area) => area.obstacles),
  );
  const authored = navigationStateAsset({
    id: "boundary",
    map: "example",
    camera: document.camera,
    patch: {
      active: true,
      definitive: false,
      waypoint: [320, 320],
      apply_sector: { points: [] },
      no_apply_sector: { points: [] },
    },
    initial: obstacles.filter((obstacle) => obstacle.state_id === 1),
    applied: obstacles.filter((obstacle) => obstacle.state_id === 2),
    receivers: [],
    groundLayer: true,
    waypointHeight: 0,
  });
  delete hut.gameplay!.movementTransitions;
  assets.set("boundary", authored.descriptor);
  document.assetSources!.push({
    id: "boundary",
    descriptor: "3d-assets/boundary/asset.json",
    model: "3d-assets/boundary/model.glb",
    model_sha256: "0".repeat(64),
    descriptor_sha256: "0".repeat(64),
  });
  document.groups.push({
    id: "boundary-a",
    transform: {
      dx: authored.origin[0],
      dy: authored.origin[1],
      dz: authored.origin[2],
      rot_deg: 0,
    },
  });
  document.objects.push({
    id: "boundary-a-frame",
    node: `asset:boundary:${authored.node}`,
    group: "boundary-a",
    kind: "scenery",
    source: { map: "example" },
    transform: { ...IDENTITY_TRANSFORM },
  });
  const after = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  assert.deepEqual(after.motion_data, before.motion_data);
  assert.deepEqual(after.sight_obstacles, before.sight_obstacles);
  assert.deepEqual(after.movement_transitions![0]!.waypoint, [320, 320]);
  const copied = structuredClone(document.objects.at(-1)!);
  copied.id = "boundary-b-frame";
  copied.group = "boundary-b";
  document.objects.push(copied);
  document.groups.push({ id: "boundary-b", transform: { ...document.groups.at(-1)!.transform } });
  const doubled = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  assert.equal(doubled.movement_transitions!.length, 2);
  assert.notDeepEqual(
    doubled.movement_transitions![0]!.motion_changes,
    doubled.movement_transitions![1]!.motion_changes,
  );
  document.groups.at(-1)!.transform.dx += 10;
  const moved = compileAssetGameplay(document, assets, [0, 0, 2000, 2000]);
  assert.deepEqual(
    moved.movement_transitions!.map((transition) => transition.waypoint),
    [
      [320, 320],
      [330, 320],
    ],
  );
});
