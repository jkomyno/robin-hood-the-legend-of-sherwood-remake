import test from "node:test";
import assert from "node:assert/strict";
import { restoreModelPartMetadata } from "./restore-model-part-metadata.ts";
import { assetCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";

test("missing source ownership is restored without changing GLB binary payload", () => {
  const { hut } = assetCompilerFixture();
  const json = Buffer.from(
    JSON.stringify({
      nodes: [
        { name: "building-999", mesh: 0, extras: { author: "retained" } },
        { name: "building-999", children: [0], extras: { asset_group: hut.id } },
      ],
    }),
  );
  const padded = Buffer.alloc(Math.ceil(json.length / 4) * 4, 32);
  json.copy(padded);
  const header = Buffer.alloc(20);
  header.writeUInt32LE(0x46546c67, 0);
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(20 + padded.length + 12, 8);
  header.writeUInt32LE(padded.length, 12);
  header.writeUInt32LE(0x4e4f534a, 16);
  const tail = Buffer.from([4, 0, 0, 0, 0x42, 0x49, 0x4e, 0, 13, 37, 42, 99]);
  const result = restoreModelPartMetadata(Buffer.concat([header, padded, tail]), hut);
  assert.deepEqual(result.restored, ["building-999.source_obstacle"]);
  assert.deepEqual(result.bytes.subarray(-12), tail);
  const document = JSON.parse(
    result.bytes.subarray(20, 20 + result.bytes.readUInt32LE(12)).toString(),
  );
  assert.deepEqual(document.nodes, [
    { name: "building-999", mesh: 0, extras: { author: "retained", source_obstacle: 999 } },
    { name: "building-999", children: [0], extras: { asset_group: hut.id } },
  ]);
  assert.deepEqual(restoreModelPartMetadata(result.bytes, hut).restored, []);
  hut.parts[0]!.source_obstacle = 123;
  assert.throws(() => restoreModelPartMetadata(result.bytes, hut), /Conflicting/);
});
