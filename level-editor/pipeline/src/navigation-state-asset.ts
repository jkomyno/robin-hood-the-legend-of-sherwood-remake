import { gameToScene, type MapCamera, type Vec3 } from "@rle/shared";
import {
  validateAssetGameplay,
  type GameplayAssetDescriptor,
} from "../../shared/src/asset-gameplay.ts";
import { recoverMovementTransition } from "./recover-movement-transition.ts";

/** Author a reusable non-rendering boundary, normalized around its own geometry. */
export function navigationStateAsset(
  options: Omit<
    Parameters<typeof recoverMovementTransition>[0],
    "id" | "node" | "localize" | "initialSight" | "appliedSight"
  > & { id: string; map: string; camera: MapCamera },
) {
  const node = "scenery-navigation-frame";
  const definition = { ...options, id: "boundary", node, initialSight: [], appliedSight: [] };
  const world = recoverMovementTransition({ ...definition, localize: (point) => point });
  const vertices = [...world.initial, ...world.applied].flatMap((surface) =>
    surface.polygon.map(([x, y], index): Vec3 => [
      x,
      y,
      typeof surface.height === "number" ? surface.height : surface.height[index]!,
    ]),
  );
  if (!vertices.length) throw new Error("Navigation asset has no changing geometry");
  const xs = vertices.map((point) => point[0]),
    ys = vertices.map((point) => point[1]);
  const origin: Vec3 = [
    (Math.min(...xs) + Math.max(...xs)) / 2,
    (Math.min(...ys) + Math.max(...ys)) / 2,
    Math.min(...vertices.map((point) => point[2])),
  ];
  const transition = recoverMovementTransition({
    ...definition,
    localize: ([x, y, z]) => [x - origin[0], y - origin[1], z - origin[2]],
  });
  const descriptor: GameplayAssetDescriptor = {
    version: 1,
    kind: "projection-mapped-asset",
    id: options.id,
    name: "Conditional navigation boundary",
    source_map: options.map,
    source_origin_scene: gameToScene(options.camera, ...origin),
    model: "model.glb",
    model_scene: "default",
    resources: [],
    parts: [{ node, name: "Navigation boundary", scenery: true, gameplay_only: true }],
    gameplay: {
      version: 1,
      collision: "none",
      surfaces: [],
      doors: [],
      movementBlockers: [],
      movementTransitions: [transition],
    },
  };
  validateAssetGameplay(descriptor.gameplay!, descriptor);
  return { descriptor, origin, node };
}
