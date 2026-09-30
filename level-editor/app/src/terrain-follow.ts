import {
  applyAffineMatrix,
  gameToScene,
  groupCentroid,
  groupParts,
  partMatrix,
  partPivot,
  sceneToGame,
  terrainHeightAt,
  type GameTransform,
  type Level3D,
  type Vec3,
} from "@rle/shared";
import type { Selection } from "./document-commands.ts";

/** Sample at a stable placement anchor, keeping a building's parts together. */
export function terrainAnchor(
  document: Level3D,
  selection: NonNullable<Selection>,
): [number, number] {
  if (selection.kind === "group") {
    const group = document.groups.find((entry) => entry.id === selection.id);
    if (!group) throw new Error(`Missing placement group: ${selection.id}`);
    const pivot = groupCentroid(groupParts(document, group.id));
    return [pivot[0] + group.transform.dx, pivot[1] + group.transform.dy];
  }
  const part = document.objects.find((entry) => entry.id === selection.id);
  if (!part) throw new Error(`Missing placement part: ${selection.id}`);
  const pivot = partPivot(part);
  const position = sceneToGame(
    document.camera,
    applyAffineMatrix(
      partMatrix(document.camera, document, part),
      gameToScene(document.camera, ...pivot, 0),
    ),
  );
  return [position[0], position[1]];
}

function withTransform(
  document: Level3D,
  selection: NonNullable<Selection>,
  transform: GameTransform,
): Level3D {
  return selection.kind === "group"
    ? {
        ...document,
        groups: document.groups.map((entry) =>
          entry.id === selection.id ? { ...entry, transform } : entry,
        ),
      }
    : {
        ...document,
        objects: document.objects.map((entry) =>
          entry.id === selection.id ? { ...entry, transform } : entry,
        ),
      };
}

/** Horizontal movement preserves the existing offset; direct Height edits stay literal. */
export function followTerrainTransform(
  document: Level3D,
  selection: NonNullable<Selection>,
  transform: GameTransform,
): GameTransform {
  if (!document.terrain) return transform;
  const before = terrainAnchor(document, selection);
  const after = terrainAnchor(withTransform(document, selection, transform), selection);
  if (before[0] === after[0] && before[1] === after[1]) return transform;
  const oldHeight = terrainHeightAt(document, ...before);
  const newHeight = terrainHeightAt(document, ...after);
  if (oldHeight === undefined || newHeight === undefined) return transform;
  return { ...transform, dz: transform.dz + newHeight - oldHeight };
}

/** Horizontal character movement preserves its authored offset above terrain. */
export function followMissionTerrain(document: Level3D, before: Vec3, after: Vec3): Vec3 {
  if (before[0] === after[0] && before[1] === after[1]) return after;
  const oldHeight = terrainHeightAt(document, before[0], before[1]);
  const newHeight = terrainHeightAt(document, after[0], after[1]);
  return oldHeight === undefined || newHeight === undefined
    ? after
    : [after[0], after[1], after[2] + newHeight - oldHeight];
}

/** A terrain gesture and its attached placements form one document/undo operation. */
export function followTerrainEdit(previous: Level3D, next: Level3D): Level3D {
  if (
    !previous.terrain ||
    !next.terrain ||
    (previous.terrain === next.terrain &&
      previous.splines === next.splines &&
      previous.camera === next.camera)
  )
    return next;
  const moved = (selection: NonNullable<Selection>, transform: GameTransform): GameTransform => {
    const anchor = terrainAnchor(next, selection);
    const before = terrainHeightAt(previous, ...anchor);
    const after = terrainHeightAt(next, ...anchor);
    return before === undefined || after === undefined || before === after
      ? transform
      : { ...transform, dz: transform.dz + after - before };
  };
  const moveActor = <T extends { position: Vec3 }>(actor: T): T => {
    const [x, y, z] = actor.position;
    const before = terrainHeightAt(previous, x, y);
    const after = terrainHeightAt(next, x, y);
    return before === undefined || after === undefined || before === after
      ? actor
      : { ...actor, position: [x, y, z + after - before] };
  };
  return {
    ...next,
    ...(next.mission
      ? {
          mission: {
            ...next.mission,
            spawnPoints: next.mission.spawnPoints.map(moveActor),
            soldiers: next.mission.soldiers.map(moveActor),
          },
        }
      : {}),
    groups: next.groups.map((group) => ({
      ...group,
      transform: moved({ kind: "group", id: group.id }, group.transform),
    })),
    objects: next.objects.map((part) =>
      part.group
        ? part
        : { ...part, transform: moved({ kind: "part", id: part.id }, part.transform) },
    ),
  };
}
