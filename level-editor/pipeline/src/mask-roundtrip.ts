import assert from "node:assert/strict";
import { isDeepStrictEqual } from "node:util";
import type { Mask } from "../../shared/src/level.ts";
import { decodeRecoveryMask } from "./recover-mask-bitmap.ts";

export function maskCoverage(mask: Mask): Set<string> {
  const pixels = decodeRecoveryMask(mask);
  const points = new Set<string>();
  for (const [i, pixel] of pixels.entries())
    if (pixel)
      points.add(
        `${mask.box_top_left[0] + (i % mask.box_size[0])},${mask.box_top_left[1] + Math.floor(i / mask.box_size[0])}`,
      );
  return points;
}

/** Layer and obstacle IDs are rebuilt, so source IDs cannot identify compiled
 * masks. Require an unambiguous pixel/rule match, including view-only records.
 * This comparison does not certify receiving-layer or obstacle ownership. */
export function matchRecoveredMasks(expected: Mask, compiled: Mask[]): number[] {
  const coverage = maskCoverage(expected);
  assert.ok(coverage.size, "Cannot identify an empty source mask");
  const matches = compiled.flatMap((mask, index) => {
    if (
      mask.mask_type !== expected.mask_type ||
      mask.obstacle_indices.length !== expected.obstacle_indices.length ||
      !isDeepStrictEqual(mask.character_polyline, expected.character_polyline) ||
      !isDeepStrictEqual(mask.projectile_polyline, expected.projectile_polyline)
    )
      return [];
    const pixels = maskCoverage(mask);
    return pixels.size && [...pixels].every((point) => coverage.has(point))
      ? [{ index, pixels }]
      : [];
  });
  const combined = new Set<string>();
  for (const { index, pixels } of matches) {
    const first = compiled[matches[0]!.index]!;
    assert.equal(compiled[index]!.layer, first.layer, "Mask tiles have different receiving layers");
    assert.deepEqual(
      compiled[index]!.obstacle_indices,
      first.obstacle_indices,
      "Mask tiles have different obstacle links",
    );
    for (const point of pixels) {
      assert.ok(!combined.has(point), "Ambiguous overlapping compiled mask tiles");
      combined.add(point);
    }
  }
  assert.equal(combined.size, coverage.size, "Expected complete compiled mask coverage");
  return matches.map((match) => match.index);
}

export function verifyMaskTranslation(before: Mask, after: Mask, dx: number): void {
  assert.ok(Number.isInteger(dx), "Mask translation must use integer pixels");
  assert.equal(after.mask_type, before.mask_type);
  assert.deepEqual(after.box_top_left, [before.box_top_left[0] + dx, before.box_top_left[1]]);
  assert.deepEqual(after.box_size, before.box_size);
  assert.deepEqual(after.mask_data, before.mask_data);
  assert.deepEqual(after.obstacle_indices, before.obstacle_indices);
  for (const key of ["character_polyline", "projectile_polyline"] as const)
    assert.deepEqual(after[key], before[key]?.map(([x, y]) => [x + dx, y]) ?? null);
}
