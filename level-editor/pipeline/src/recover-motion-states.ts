import type { MotionArea, MotionObstacle, Patch } from "../../shared/src/level.ts";

/** Separate permanent terrain from changing exclusions for one-time asset authoring. */
export function recoverMotionStates(
  area: MotionArea,
  sector: number,
  layer: number,
  patches: Patch[],
) {
  if (area.state_id !== 0)
    throw new Error("State-dependent movement-area boundaries need explicit authoring");
  const stable: MotionObstacle[] = [];
  const changing = new Map<
    number,
    { pair: number; patches: number[]; initial: MotionObstacle[]; applied: MotionObstacle[] }
  >();
  for (const obstacle of area.obstacles) {
    const state = obstacle.state_id;
    if (typeof state !== "number" || !Number.isInteger(state) || state < 0 || state > 0xffffffff)
      throw new Error("Invalid movement obstacle state mask");
    if (state === 0) {
      stable.push(obstacle);
      continue;
    }
    if ((state & (state - 1)) !== 0)
      throw new Error("Combined movement state masks need explicit authoring");
    const bit = Math.log2(state),
      pair = Math.floor(bit / 2);
    let transition = changing.get(pair);
    if (!transition) {
      transition = {
        pair,
        initial: [],
        applied: [],
        patches: patches.flatMap((patch, index) =>
          patch.pathfinder_sector === sector &&
          patch.pathfinder_layer === layer &&
          patch.pathfinder_changing_obstacles === pair
            ? [index]
            : [],
        ),
      };
      changing.set(pair, transition);
    }
    (bit % 2 === 0 ? transition.initial : transition.applied).push(obstacle);
  }
  return { base: { ...area, obstacles: stable }, transitions: [...changing.values()] };
}
