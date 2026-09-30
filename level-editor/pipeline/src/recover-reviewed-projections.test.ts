import test from "node:test";
import assert from "node:assert/strict";
import { projectionMaterialCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { transformedObstacle } from "../../shared/src/level3d.ts";
import type { RecoveredGameplayPacket } from "./recovered-gameplay-definition.ts";
import {
  recoverReviewedProjections,
  type ReviewedProjections,
} from "./recover-reviewed-projections.ts";

function fixture() {
  const { document, assets, hut } = projectionMaterialCompilerFixture();
  const surface = hut.gameplay!.surfaces[0]!;
  const part = document.objects.find((p) => p.node.endsWith(":building-999"))!;
  const definition = hut.parts[0]!;
  definition.obstacle_local_game = {
    ...definition.obstacle_local_game!,
    points: surface.polygon.map(([x, y]) => ({ x, y, z_bottom: 15, z_top: 20 })),
    projection_area: null,
    material_indices: [],
  };
  const original = transformedObstacle(document, {
    ...part,
    obstacle: definition.obstacle_local_game,
  });
  original.projection_area = [1, 1];
  const source = { sight_obstacles: Array.from({ length: 1000 }, () => structuredClone(original)) };
  const packet: RecoveredGameplayPacket = {
    asset: "hut",
    connections: [],
    materials: structuredClone(hut.gameplay!.materials),
    surfaces: [
      {
        id: surface.id,
        node: surface.node,
        vertices: surface.polygon.map(([x, y]) => [x, y, 20]),
        holes: [],
        projectionMaterials: structuredClone(surface.projectionMaterials),
      },
    ],
  };
  const packets = new Map([["hut", packet]]);
  const definitions: ReviewedProjections = {
    source_sha256: "source-pin",
    entries: [
      {
        asset: "hut",
        model_sha256: "0".repeat(64),
        surface: surface.id,
        node: surface.node,
        source_obstacle: 999,
      },
    ],
  };
  const recover = () =>
    recoverReviewedProjections(document, assets, source, "source-pin", definitions, packets);
  return { document, source, packet, definitions, recover };
}

test("reviewed projections produce local physical and material links", () => {
  const { packet, definitions, recover } = fixture();
  const report = recover();
  assert.deepEqual(report, definitions.entries);
  assert.equal(packet.surfaces[0]!.projectionVolume, "building-999");
  assert.equal(packet.surfaces[0]!.projectionMaterials, undefined);
  assert.deepEqual(packet.materials![0]!.obstacles, ["building-999"]);
  assert.equal(JSON.stringify(packet).includes("source_obstacle"), false);
});

test("reviewed projection failures leave every packet unchanged", () => {
  for (const change of [
    (f: ReturnType<typeof fixture>) => {
      f.definitions.source_sha256 = "stale";
    },
    (f: ReturnType<typeof fixture>) => {
      f.definitions.entries[0]!.model_sha256 = "stale";
    },
    (f: ReturnType<typeof fixture>) => {
      f.source.sight_obstacles[999]!.points[0]!.z_bottom += 1;
    },
    (f: ReturnType<typeof fixture>) => {
      f.definitions.entries.push({ ...f.definitions.entries[0]! });
    },
    (f: ReturnType<typeof fixture>) => {
      f.definitions.entries.push({ ...f.definitions.entries[0]!, surface: "missing" });
    },
    (f: ReturnType<typeof fixture>) => {
      f.packet.materials = [];
    },
    (f: ReturnType<typeof fixture>) => {
      const copy = structuredClone(
        f.document.objects.find((p) => p.node.endsWith(":building-999"))!,
      );
      copy.id += "-copy";
      copy.node = "asset:other:building-999";
      f.document.objects.push(copy);
    },
  ]) {
    const f = fixture();
    change(f);
    const before = structuredClone(f.packet);
    assert.throws(f.recover, /Reviewed projection|Duplicate reviewed projection/);
    assert.deepEqual(f.packet, before);
  }
});
