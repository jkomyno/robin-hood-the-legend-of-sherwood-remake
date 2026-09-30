import type { Point, SightObstacle } from "../../shared/src/level.ts";

/** Baseline extraction audit only: compare ordered anchor values at native
 * float32 precision. This does not establish receiving ownership, coverage,
 * overlap priority or actor traversal. Offset is the export frame's XY origin. */
export function compareReceivingPlaneAnchors(
  source: SightObstacle[],
  compiled: SightObstacle[],
  offset: Point = [0, 0],
) {
  const buffer = new DataView(new ArrayBuffer(4));
  const bits = (value: number) => {
    if (!Number.isFinite(Math.fround(value)))
      throw new Error("Receiving plane anchor is not finite at native precision");
    buffer.setFloat32(0, value);
    return buffer.getUint32(0);
  };
  const key = (points: number[][]) => {
    if (points.length !== 3 || points.some((point) => point.length !== 3))
      throw new Error("Receiving plane requires three ordered 3D anchors");
    return points.flat().map(bits).join(",");
  };
  const expected = new Set(
    source
      .filter((o) => Array.isArray(o.projection_area))
      .map((o) => {
        if (o.points.length < 3) throw new Error("Source receiver has no plane anchors");
        return key(
          [o.points[1]!, o.points[2]!, o.points[0]!].map((p) => [
            p.x - offset[0],
            p.y - offset[1],
            p.z_top,
          ]),
        );
      }),
  );
  let compared = 0,
    unanchored = 0;
  const differences: { obstacle: number; plane: NonNullable<SightObstacle["projection_plane"]> }[] =
    [];
  for (const [index, obstacle] of compiled.entries()) {
    if (!Array.isArray(obstacle.projection_area)) continue;
    if (!obstacle.projection_plane) {
      unanchored++;
      continue;
    }
    compared++;
    if (!expected.has(key(obstacle.projection_plane)))
      differences.push({ obstacle: index, plane: obstacle.projection_plane });
  }
  return { compared, unanchored, allMatch: compared > 0 && !differences.length, differences };
}
