import { mat4 } from "gl-matrix";
import {
  gameTransformMatrix,
  groupCentroid,
  groupParts,
  isIdentity,
  obstacleCentroid,
  partMatrix,
  type GameTransform,
  type Level3D,
} from "@rle/shared";

export interface AuthoredGltf {
  nodes: {
    name?: string;
    children?: number[];
    extras?: { part_name?: string; asset_group?: string };
  }[];
}

function layout(gltf: AuthoredGltf) {
  const root = gltf.nodes.find((node) => node.name === "map");
  if (!root) throw new Error("Refined map lacks editor root");
  const groups = new Map<string, string>();
  const owners = new Map<string, string>();
  for (const index of root.children ?? []) {
    const group = gltf.nodes[index]!;
    if (group.name === "ground") continue;
    const id = group.extras?.asset_group;
    if (!id || !group.name || groups.has(id))
      throw new Error("Missing or duplicate authored group ID");
    groups.set(id, group.name);
    for (const child of group.children ?? []) {
      const name = gltf.nodes[child]?.name;
      if (!name || owners.has(name)) throw new Error("Missing or duplicate refined part ID");
      owners.set(name, id);
    }
  }
  return { groups, owners };
}

/** Recover an editor transform from a scene matrix at the given editor pivot. */
export function transformAt(
  document: Level3D,
  matrix: ArrayLike<number>,
  pivot: [number, number],
): GameTransform {
  const angle = Math.atan2(matrix[4]!, matrix[0]!);
  const k = -1 / Math.sin((document.camera.elevation_deg * Math.PI) / 180);
  const x = pivot[0],
    y = pivot[1] * k;
  const c = Math.cos(angle),
    s = Math.sin(angle);
  const clean = (value: number) => (Math.abs(value) < 1e-9 ? 0 : value);
  return {
    dx: clean(matrix[12]! - (x - c * x - s * y)),
    dy: clean((matrix[13]! - (y + s * x - c * y)) / k),
    dz: clean(matrix[14]! * Math.cos((document.camera.elevation_deg * Math.PI) / 180)),
    rot_deg: clean((angle * 180) / Math.PI),
  };
}

/** Three-way merge authored ownership while retaining map-author edits and world poses. */
export function mergeRefinedGroups(
  document: Level3D,
  previous: AuthoredGltf,
  refined: AuthoredGltf,
) {
  const before = layout(previous),
    after = layout(refined);
  const previousNodes = new Map(previous.nodes.map((node) => [node.name, node]));
  const refinedNodes = new Map(refined.nodes.map((node) => [node.name, node]));
  const oldGroups = new Map(document.groups.map((group) => [group.id, structuredClone(group)]));
  const groupMatrices = new Map(
    document.groups.map((group) => [
      group.id,
      gameTransformMatrix(
        document.camera,
        group.transform,
        groupCentroid(groupParts(document, group.id)),
      ),
    ]),
  );
  const worldMatrices = new Map(
    document.objects.map((part) => [part.id, partMatrix(document.camera, document, part)]),
  );
  const moved = new Map<string, number[]>();
  const affected = new Set<string>();
  const created: string[] = [];
  for (const part of document.objects) {
    const oldName = previousNodes.get(part.node)?.extras?.part_name;
    const newName = refinedNodes.get(part.node)?.extras?.part_name;
    if (oldName && newName && part.name === oldName) part.name = newName;
    const source = before.owners.get(part.node),
      destination = after.owners.get(part.node);
    // Copies, explicit ungrouping, and custom reparenting belong to the map author.
    if (
      part.id !== part.node ||
      !source ||
      !destination ||
      source === destination ||
      part.group !== source
    )
      continue;
    const target = document.groups.find((group) => group.id === destination);
    // Do not silently join an unrelated user-created group with the same ID,
    // or change visible parts by placing them inside a hidden group.
    if (
      target &&
      ((!before.groups.has(destination) && !created.includes(destination)) || target.hidden)
    )
      continue;
    moved.set(part.id, worldMatrices.get(part.id)!);
    if (oldGroups.get(source)?.hidden) part.hidden = true;
    if (!target) {
      document.groups.push({
        id: destination,
        name: after.groups.get(destination)!,
        transform: { dx: 0, dy: 0, dz: 0, rot_deg: 0 },
      });
      created.push(destination);
    }
    affected.add(source);
    affected.add(destination);
    part.group = destination;
  }
  // Ownership changes alter centroid-based pivots. Retain each existing group's
  // affine transform so even unmoved/custom members stay exactly in place.
  for (const group of document.groups) {
    const oldMatrix = groupMatrices.get(group.id);
    if (affected.has(group.id) && oldMatrix)
      group.transform = transformAt(
        document,
        oldMatrix,
        groupCentroid(groupParts(document, group.id)),
      );
    const oldName = before.groups.get(group.id),
      newName = after.groups.get(group.id);
    if (oldName && newName && group.name === oldName) group.name = newName;
  }
  for (const part of document.objects) {
    const world = moved.get(part.id);
    if (!world) continue;
    const group = document.groups.find((group) => group.id === part.group)!;
    const matrix = gameTransformMatrix(
      document.camera,
      group.transform,
      groupCentroid(groupParts(document, group.id)),
    );
    const inverse = mat4.invert(new Float64Array(16), matrix);
    if (!inverse) throw new Error(`Cannot preserve transform for ${part.id}`);
    const local = mat4.multiply(new Float64Array(16), inverse, world);
    part.transform = transformAt(document, local, obstacleCentroid(part.obstacle.points));
  }
  const removed: string[] = [];
  document.groups = document.groups.filter((group) => {
    const old = oldGroups.get(group.id);
    const safe =
      old &&
      before.groups.has(group.id) &&
      !after.groups.has(group.id) &&
      old.name === before.groups.get(group.id) &&
      !old.hidden &&
      isIdentity(old.transform) &&
      !document.objects.some((part) => part.group === group.id);
    if (safe) removed.push(group.id);
    return !safe;
  });
  return {
    nodes: new Set(after.owners.keys()),
    migratedParts: [...moved.keys()],
    createdGroups: created,
    removedGroups: removed,
  };
}

/** Preserve placed poses when a revised local asset uses a different export origin. */
export function rebaseLibraryRevision(document: Level3D, staged: Level3D) {
  const oldOrigins = document.sceneMetadata?.assetOrigins as
    | Record<string, [number, number, number]>
    | undefined;
  const newOrigins = staged.sceneMetadata?.assetOrigins as
    | Record<string, [number, number, number]>
    | undefined;
  if (!oldOrigins || !newOrigins)
    throw new Error("Local asset revision requires map placement origins");
  const sourceName = (node: string) =>
    node.startsWith("asset:") ? node.split(":").slice(2).join(":") : node;
  const replacements = new Map(staged.objects.map((part) => [sourceName(part.node), part]));
  const desired = new Map<string, mat4>();
  const offsets = new Map<string, [number, number, number]>();
  const oldGroups = new Map(
    document.groups.map((group) => [
      group.id,
      gameTransformMatrix(
        document.camera,
        group.transform,
        groupCentroid(groupParts(document, group.id)),
      ),
    ]),
  );
  for (const part of document.objects) {
    const next = replacements.get(sourceName(part.node));
    if (!next) throw new Error(`Revised map is missing source part ${part.node}`);
    const oldId = part.node.split(":")[1]!,
      newId = next.node.split(":")[1]!;
    if (!oldOrigins[oldId] || !newOrigins[newId])
      throw new Error(`Missing asset origin: ${part.id}`);
    const delta = newOrigins[newId].map((value, index) => value - oldOrigins[oldId]![index]!) as [
      number,
      number,
      number,
    ];
    desired.set(
      part.id,
      mat4.multiply(
        new Float64Array(16),
        partMatrix(document.camera, document, part),
        mat4.fromTranslation(new Float64Array(16), delta),
      ),
    );
    offsets.set(part.id, delta);
  }
  for (const part of document.objects) {
    const next = replacements.get(sourceName(part.node))!;
    part.node = next.node;
    part.obstacle = structuredClone(next.obstacle);
    part.source = structuredClone(next.source);
    part.missionBindings = structuredClone(next.missionBindings);
  }
  for (const group of document.groups) {
    const members = groupParts(document, group.id);
    const delta = members.length
      ? offsets.get(members[0]!.id)!
      : ([0, 0, 0] as [number, number, number]);
    const matrix = mat4.multiply(
      new Float64Array(16),
      oldGroups.get(group.id)!,
      mat4.fromTranslation(new Float64Array(16), delta),
    );
    group.transform = transformAt(document, matrix, groupCentroid(members));
  }
  for (const part of document.objects) {
    let matrix = desired.get(part.id)!;
    if (part.group) {
      const group = document.groups.find((group) => group.id === part.group)!;
      const inverse = mat4.invert(
        new Float64Array(16),
        gameTransformMatrix(
          document.camera,
          group.transform,
          groupCentroid(groupParts(document, group.id)),
        ),
      );
      if (!inverse) throw new Error(`Singular group transform: ${group.id}`);
      matrix = mat4.multiply(new Float64Array(16), inverse, matrix);
    }
    part.transform = transformAt(document, matrix, obstacleCentroid(part.obstacle.points));
  }
  document.assetSources = structuredClone(staged.assetSources);
  document.sceneAssets = structuredClone(staged.sceneAssets);
  document.sceneMetadata = structuredClone(staged.sceneMetadata);
  return document;
}
