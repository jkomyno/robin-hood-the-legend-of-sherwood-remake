import test from "node:test";
import assert from "node:assert/strict";
import type { Mask } from "../../shared/src/level.ts";
import type { Vec3 } from "../../shared/src/scene.ts";
import {
  rasterizeMaskGeometry,
  type MaskTriangle,
} from "../../shared/src/compile-mask-geometry.ts";
import { encodeMaskBitmap } from "../../shared/src/encode-mask-bitmap.ts";
import { decodeRecoveryMask } from "./recover-mask-bitmap.ts";
import { recoverMaskSurface } from "./recover-mask-surface.ts";

const identity = (p: Vec3) => p;
const mask = (rows: string[]): Mask => ({
  layer: 0,
  mask_type: 4,
  character_polyline: null,
  projectile_polyline: null,
  obstacle_indices: [],
  box_top_left: [0, 0],
  box_size: [rows[0]!.length, rows.length],
  mask_data: encodeMaskBitmap(Uint8Array.from(rows.join(""), Number), rows[0]!.length, rows.length),
});
const surface = (z: (x: number) => number): MaskTriangle[] => {
  const points: Vec3[] = [
    [0, 0],
    [4, 0],
    [4, 4],
    [0, 4],
  ].map(([x, y]) => [x!, y! + z(x!), z(x!)]);
  return [
    [points[0]!, points[1]!, points[2]!],
    [points[0]!, points[2]!, points[3]!],
  ];
};

test("partial edge cells recover only when compiler pixel samples remain exact", () => {
  const source = mask(["1111", "1111", "1111", "1111"]);
  const inset = (amount: number) =>
    surface(() => 0).map(
      (t) =>
        t.map(([x, y, z]): Vec3 => [
          amount + x * (1 - amount / 2),
          amount + y * (1 - amount / 2),
          z,
        ]) as MaskTriangle,
    );
  assert.ok(recoverMaskSurface(source, inset(0.1), identity).length > 0);
  assert.throws(() => recoverMaskSurface(source, inset(0.6), identity), /no owner surface/);
});

test("surface recovery preserves cutouts on sloped geometry and localizes once", () => {
  const source = mask(["1111", "1001", "1001", "1111"]);
  const recovered = recoverMaskSurface(
    source,
    surface((x) => 10 + x),
    ([x, y, z]) => [x - 100, y - 200, z - 5],
  );
  const placed = recovered.map(
    (t) => t.map(([x, y, z]): Vec3 => [x + 100, y + 200, z + 5]) as MaskTriangle,
  );
  assert.ok(placed.flat().every(([x, , z]) => Math.abs(z - 10 - x) < 1e-8));
  const result = rasterizeMaskGeometry(placed, source);
  assert.equal(result.length, 1);
  assert.deepEqual(decodeRecoveryMask(result[0]!), decodeRecoveryMask(source));
  assert.deepEqual(result[0]!.box_top_left, source.box_top_left);
});

test("crossing faces split at the visible depth boundary regardless of input order", () => {
  const source = mask(["1111", "1111", "1111", "1111"]);
  const faces = [...surface((x) => x), ...surface((x) => 4 - x)];
  for (const order of [faces, [...faces].reverse(), [...faces, ...faces]]) {
    const recovered = recoverMaskSurface(source, order, identity);
    for (const triangle of recovered) {
      const center = triangle.reduce((sum, p) => sum + p[0], 0) / 3;
      const depth = triangle.reduce((sum, p) => sum + p[2], 0) / 3;
      assert.ok(Math.abs(depth - Math.max(center, 4 - center)) < 1e-8);
    }
    const projectedArea = recovered.reduce(
      (sum, [a, b, c]) =>
        sum +
        Math.abs(
          (b[0] - a[0]) * (c[1] - c[2] - (a[1] - a[2])) -
            (c[0] - a[0]) * (b[1] - b[2] - (a[1] - a[2])),
        ) /
          2,
      0,
    );
    assert.ok(
      Math.abs(projectedArea - 16) < 1e-8,
      "hidden or duplicate faces must not retain coverage",
    );
    assert.deepEqual(
      decodeRecoveryMask(rasterizeMaskGeometry(recovered, source)[0]!),
      decodeRecoveryMask(source),
    );
  }
});

test("surface recovery rejects missing geometry rather than extrapolating heights", () => {
  const source = mask(["1111", "1111", "1111", "1111"]);
  assert.throws(() => recoverMaskSurface(source, [], identity), /no owner surface/);
  assert.throws(
    () => recoverMaskSurface(source, surface(() => 0).slice(0, 1), identity),
    /no owner surface/,
  );
  assert.throws(
    () =>
      recoverMaskSurface(
        source,
        [
          [
            [0, 0, 0],
            [0, 4, 0],
            [0, 4, 4],
          ],
        ],
        identity,
      ),
    /no owner surface/,
  );
  assert.throws(
    () =>
      recoverMaskSurface(
        source,
        surface(() => NaN),
        identity,
      ),
    /Invalid/,
  );
  assert.throws(
    () =>
      recoverMaskSurface(
        source,
        surface(() => 0),
        () => [NaN, 0, 0],
      ),
    /Invalid/,
  );
});

test("a foreground island cuts a hole in the recovered background surface", () => {
  const source = mask(["1111", "1111", "1111", "1111"]);
  const foreground = surface(() => 5).map(
    (t) => t.map(([x, y, z]): Vec3 => [1 + x / 2, 1 + (y - z) / 2 + z, z]) as MaskTriangle,
  );
  const recovered = recoverMaskSurface(source, [...surface(() => 0), ...foreground], identity);
  let frontArea = 0,
    backArea = 0;
  for (const [a, b, c] of recovered) {
    const area =
      Math.abs(
        (b[0] - a[0]) * (c[1] - c[2] - (a[1] - a[2])) -
          (c[0] - a[0]) * (b[1] - b[2] - (a[1] - a[2])),
      ) / 2;
    if (a[2] === 5) frontArea += area;
    else backArea += area;
  }
  assert.equal(frontArea, 4);
  assert.equal(backArea, 12);
  assert.deepEqual(
    decodeRecoveryMask(rasterizeMaskGeometry(recovered, source)[0]!),
    decodeRecoveryMask(source),
  );
});
