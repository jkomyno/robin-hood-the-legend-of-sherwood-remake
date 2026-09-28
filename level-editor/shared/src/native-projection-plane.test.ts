import assert from "node:assert/strict";
import test from "node:test";
import { writeFileSync } from "node:fs";
import { nativeProjectionPlane, equivalentProjectionPlanes } from "./native-projection-plane.ts";
import type { SightObstacle } from "./level.ts";

const buffer = new ArrayBuffer(4),
  bits = new DataView(buffer);
const float = (value: number) => {
  bits.setUint32(0, value, true);
  return bits.getFloat32(0, true);
};
const word = (value: number) => {
  bits.setFloat32(0, value, true);
  return bits.getUint32(0, true);
};

test(
  "emit deterministic receiving-plane fixtures for native verification",
  {
    skip: !process.env.ROBIN_PROJECTION_PLANE_CASES,
  },
  () => {
    let seed = 319;
    const random = () => (seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296;
    const cases = [];
    for (let i = 0; i < 10000; i++) {
      const height = random() * 800;
      const point = (): [number, number, number] => [
        random() * 5000,
        random() * 5000,
        i % 2 ? height : random() * 800,
      ];
      const points: NonNullable<SightObstacle["projection_plane"]> = [point(), point(), point()];
      const coefficients = nativeProjectionPlane(points);
      assert(coefficients);
      cases.push({ points, expected: coefficients.map(word) });
    }
    writeFileSync(process.env.ROBIN_PROJECTION_PLANE_CASES!, JSON.stringify(cases));
  },
);
test("plane coefficients retain runtime binary32 rounding", () => {
  const anchors: NonNullable<SightObstacle["projection_plane"]> = [
    [float(0x440ca539), float(0x44fdfbe4), float(0x43160042)],
    [float(0x42db66b4), float(0x44ef68a9), float(0x3a83126f)],
    [float(0x441ac40e), float(0x44f4f65d), float(0x43160042)],
  ];
  assert.deepEqual(nativeProjectionPlane(anchors)!.map(word), [0x3e8d246a, 0x3e5ce9d4, 0xc3ddb755]);
});
test("translated flat anchors are equivalent without normalizing the authored points", () => {
  const anchors: NonNullable<SightObstacle["projection_plane"]> = [
    [2377.3467, 1811.542, 350.001],
    [2392.036, 1818.0018, 350.001],
    [2488.2346, 1664.2605, 350.001],
  ];
  const moved = anchors.map(([x, y, z]) => [x + 1, y, z]) as typeof anchors;
  const before = structuredClone(anchors);
  assert(equivalentProjectionPlanes(anchors, moved));
  assert.deepEqual(anchors, before);
  moved[1][2] += 0.001;
  assert(!equivalentProjectionPlanes(anchors, moved));
  assert(!equivalentProjectionPlanes(anchors, undefined));
  assert.equal(
    nativeProjectionPlane([
      [0, 0, 0],
      [1, 0, 0],
      [2, 0, 0],
    ]),
    undefined,
  );
});

test("receiving-plane orientation preserves native signed-zero coefficients", () => {
  const anchors: NonNullable<SightObstacle["projection_plane"]> = [
    [1048.2462, 1518.7815, 100.00101],
    [1080.4686, 1539.0594, 100.00101],
    [1222.9685, 1457.3927, 100.00101],
  ];
  const coefficients = nativeProjectionPlane(anchors)!;
  assert.equal(word(coefficients[0]), 0);
  assert.equal(word(coefficients[1]), 0x80000000);
  assert(equivalentProjectionPlanes(anchors, [anchors[0], anchors[2], anchors[1]]));
});
