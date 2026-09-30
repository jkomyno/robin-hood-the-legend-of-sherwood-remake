import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { encode } from "fast-png";
import { packageAppearanceRegions, type BakedAppearanceRegion } from "./map-appearance.ts";

const pixels = (color: number[], depth: number[]) => ({
  color: Uint8Array.from(depth.flatMap(() => [...color, 255])),
  depth: Uint16Array.from(depth),
});
const base = pixels([255, 255, 255], [5, 10, 15, 20]);
const regions: BakedAppearanceRegion[] = [
  {
    bounds: [1, 0, 1, 2],
    patches: ["roof", "gate"],
    states: [
      pixels([255, 255, 255], [10, 20]),
      pixels([255, 0, 0], [1000, 1001]),
      pixels([0, 255, 0], [2000, 2001]),
      pixels([0, 0, 255], [3000, 3001]),
    ],
  },
  {
    bounds: [0, 1, 1, 1],
    patches: ["gate"],
    states: [pixels([255, 255, 255], [15]), pixels([255, 255, 0], [4000])],
  },
];
const transitions = [{ id: "gate" }, { id: "roof" }];
const prefix = "Data/Levels/Day/appearance-contract";

test("paired appearance PNG files match the Rust decoder and compositor fixture", () => {
  const files = {
    ...packageAppearanceRegions(prefix, 2, 2, base, regions, transitions),
    [`${prefix}.map.png`]: encode({ width: 2, height: 2, channels: 4, depth: 8, data: base.color }),
    [`${prefix}.occlusion-depth.png`]: encode({
      width: 2,
      height: 2,
      channels: 1,
      depth: 16,
      data: base.depth,
    }),
  };
  const fixture = JSON.parse(
    readFileSync(
      new URL("../../../crates/robin_rs/tests/fixtures/map-appearance.json", import.meta.url),
      "utf8",
    ),
  );
  assert.deepEqual(
    Object.fromEntries(
      Object.entries(files).map(([path, bytes]) => [path, Buffer.from(bytes).toString("base64")]),
    ),
    fixture,
  );
});

test("appearance packaging rejects incomplete or conflicting state tables", () => {
  assert.throws(
    () => packageAppearanceRegions(prefix, 2, 2, base, [], [{ id: "roof", has_appearance: true }]),
    /Missing rendered appearance states/,
  );
  assert.throws(
    () =>
      packageAppearanceRegions(prefix, 2, 2, base, regions.slice(1), [
        { id: "gate" },
        { id: "roof", has_appearance: true },
      ]),
    /Missing rendered appearance states/,
  );
  const invalid: [string, (regions: BakedAppearanceRegion[]) => void][] = [
    [
      "outside",
      (r) => {
        r[0]!.bounds[0] = 2;
      },
    ],
    [
      "Overlapping",
      (r) => {
        r[1]!.bounds[0] = 1;
      },
    ],
    [
      "distinct",
      (r) => {
        r[0]!.patches[1] = "roof";
      },
    ],
    [
      "Unresolved",
      (r) => {
        r[0]!.patches[0] = "unknown";
      },
    ],
    [
      "combinations",
      (r) => {
        r[0]!.states.pop();
      },
    ],
    [
      "dimensions",
      (r) => {
        r[0]!.states[1]!.depth = new Uint16Array(0);
      },
    ],
    [
      "opaque",
      (r) => {
        r[0]!.states[1]!.color[3] = 0;
      },
    ],
    [
      "base bake",
      (r) => {
        r[0]!.states[0]!.depth[0] = 0;
      },
    ],
  ];
  for (const [error, mutate] of invalid) {
    const candidate = structuredClone(regions);
    mutate(candidate);
    assert.throws(
      () => packageAppearanceRegions(prefix, 2, 2, base, candidate, transitions),
      new RegExp(error),
    );
  }
});
