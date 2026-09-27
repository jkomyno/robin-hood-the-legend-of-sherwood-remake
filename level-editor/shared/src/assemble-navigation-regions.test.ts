import test from "node:test";
import assert from "node:assert/strict";
import { assembleNavigationRegions, type NavigationPiece } from "./assemble-navigation-regions.ts";

test("joined planes preserve holes with native obstacle winding and disconnected components", () => {
  const pieces: NavigationPiece[] = [
    {
      navigationRegion: "roof",
      plane: [0, 0, 20],
      layer: 1,
      polygon: [
        [0, 0],
        [50, 0],
        [50, 100],
        [0, 100],
      ],
      blockers: [
        [
          [10, 10],
          [10, 20],
          [20, 20],
          [20, 10],
        ],
      ],
    },
    {
      navigationRegion: "roof",
      plane: [1, 0, -30],
      layer: 2,
      polygon: [
        [50, 0],
        [100, 0],
        [100, 100],
        [50, 100],
      ],
      blockers: [],
    },
    {
      navigationRegion: "roof",
      plane: [0, 0, 50],
      layer: 3,
      polygon: [
        [200, 0],
        [300, 0],
        [300, 100],
        [200, 100],
      ],
      blockers: [],
    },
  ];
  const result = assembleNavigationRegions(pieces, []);
  assert.equal(result.length, 2);
  const joined = result.find((r) => r.pieces.length === 2)!;
  assert.equal(joined.layer, 1);
  assert.equal(joined.blockers.length, 1);
  const area = joined.blockers[0]!.reduce((sum, p, i, ring) => {
    const q = ring[(i + 1) % ring.length]!;
    return sum + p[0] * q[1] - q[0] * p[1];
  }, 0);
  assert.equal(area, 200);
});
