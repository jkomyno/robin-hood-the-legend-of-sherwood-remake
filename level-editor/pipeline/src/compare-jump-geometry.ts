/** Offline parity check. Runtime indices are rebuilt, so compare geometry and rules. */
import fs from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { canonical } from "./bundle-asset-states.ts";

interface JumpLine {
  point_a: number[];
  point_b: number[];
  jump_zone_index: number;
}
export interface JumpGeometry {
  jump_zones: { polygon: { points: number[][] }; helper_needed: boolean }[];
  jump_line_pairs: { line1: JumpLine; line2: JumpLine; jump_long: boolean }[];
}

function ringKey(points: number[][]) {
  if (points.length < 3) throw new Error("Invalid jump polygon");
  const rotations = [];
  for (const order of [points, [...points].reverse()])
    for (let index = 0; index < order.length; index++)
      rotations.push(canonical([...order.slice(index), ...order.slice(0, index)]));
  return rotations.sort()[0]!;
}

function signatures(data: JumpGeometry) {
  return data.jump_line_pairs
    .map((pair) =>
      canonical({
        long: pair.jump_long,
        lines: [pair.line1, pair.line2]
          .map((line) => {
            const zone = data.jump_zones[line.jump_zone_index];
            if (!zone) throw new Error("Missing jump zone");
            return canonical({
              a: line.point_a,
              b: line.point_b,
              helper: zone.helper_needed,
              polygon: ringKey(zone.polygon.points),
            });
          })
          .sort(),
      }),
    )
    .sort();
}

export function compareJumpGeometry(source: JumpGeometry, compiled: JumpGeometry) {
  const expected = signatures(source);
  const remaining = signatures(compiled);
  const missing: string[] = [];
  for (const signature of expected) {
    const index = remaining.indexOf(signature);
    if (index < 0) missing.push(signature);
    else remaining.splice(index, 1);
  }
  return {
    sourcePairs: expected.length,
    compiledPairs: compiled.jump_line_pairs.length,
    equivalent: !missing.length && !remaining.length,
    missing,
    extra: remaining,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [source, compiled] = process.argv.slice(2);
  if (!source || !compiled)
    throw new Error("Usage: compare-jump-geometry.ts SOURCE_JSON COMPILED_LEVEL_JSON");
  const result = compareJumpGeometry(
    JSON.parse(await fs.readFile(source, "utf8")),
    JSON.parse(await fs.readFile(compiled, "utf8")).asset_geometry,
  );
  console.log(JSON.stringify(result, null, 2));
  if (!result.equivalent) process.exitCode = 1;
}
