import assert from "node:assert/strict";
import test from "node:test";
import { partMatrix, type Level3D } from "@rle/shared";
import { mergeRefinedGroups, type AuthoredGltf } from "./refined-map-groups.ts";

const identity = () => ({ dx: 0, dy: 0, dz: 0, rot_deg: 0 });
function gltf(groups: Record<string, string[]>): AuthoredGltf {
  const nodes: AuthoredGltf["nodes"] = [{ name: "map", children: [] }];
  for (const [id, parts] of Object.entries(groups)) {
    nodes[0]!.children!.push(nodes.length);
    const group = { name: id, extras: { asset_group: id }, children: [] as number[] };
    nodes.push(group);
    for (const part of parts) {
      group.children.push(nodes.length);
      nodes.push({ name: part, extras: { part_name: `Name ${part}` } });
    }
  }
  return { nodes };
}
function fixture(): Level3D {
  return {
    version: 1,
    map: "test",
    size: [100, 100],
    sceneAssets: [],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    groups: ["hall", "stairs", "yard", "custom"].map((id) => ({
      id,
      name: id,
      transform: identity(),
    })),
    objects: ["a", "b", "c", "d", "e"].map((node, i) => ({
      id: node,
      node,
      kind: "building",
      source: { map: "test", obstacle: i },
      name: `Name ${node}`,
      group: ["hall", "stairs", "stairs", "yard", "custom"][i],
      transform: identity(),
      obstacle: {
        points: [
          { x: i * 10, y: i * 20, z_bottom: 0, z_top: 10 },
          { x: i * 10 + 4, y: i * 20, z_bottom: 0, z_top: 10 },
          { x: i * 10, y: i * 20 + 4, z_bottom: 0, z_top: 10 },
        ],
        projection_area: null,
        opaque: true,
        solid: true,
        mouse: true,
        show_shadow_polygon: true,
        default_material: 0,
        material_indices: [],
      },
    })),
  };
}
const previous = () => gltf({ hall: ["a"], stairs: ["b", "c"], yard: ["d", "e"] });
const refined = () => gltf({ hall: ["a", "b", "c"], trough: ["d", "e"] });

test("migrates authored ownership, creates groups, and retains custom membership and labels", () => {
  const document = fixture();
  document.groups[0]!.name = "My hall";
  document.objects[1]!.name = "My steps";
  const result = mergeRefinedGroups(document, previous(), refined());
  assert.deepEqual(result.migratedParts, ["b", "c", "d"]);
  assert.deepEqual(result.createdGroups, ["trough"]);
  assert.deepEqual(result.removedGroups, ["stairs", "yard"]);
  assert.equal(document.objects[4]!.group, "custom");
  assert.equal(document.objects[1]!.name, "My steps");
  assert.equal(document.groups[0]!.name, "My hall");
  assert.equal(document.objects[3]!.group, "trough");
  assert.deepEqual(mergeRefinedGroups(document, refined(), refined()).migratedParts, []);
});

test("reparenting keeps all world transforms when both groups rotate and pivots change", () => {
  const document = fixture();
  document.groups[0]!.transform = { dx: 19, dy: -3, dz: 12, rot_deg: 43 };
  document.groups[1]!.transform = { dx: -13, dy: 31, dz: 5, rot_deg: -28 };
  document.objects[2]!.transform = { dx: 11, dy: 7, dz: 2, rot_deg: 14 };
  const matrices = document.objects.map((part) => partMatrix(document.camera, document, part));
  mergeRefinedGroups(document, previous(), refined());
  document.objects.forEach((part, i) =>
    partMatrix(document.camera, document, part).forEach((value, j) =>
      assert.ok(Math.abs(value - matrices[i]![j]!) < 1e-8, `${part.id} matrix component ${j}`),
    ),
  );
  assert.ok(
    document.groups.some((group) => group.id === "stairs"),
    "edited empty groups are retained",
  );
});

test("new groups accept multiple parts, while hidden or colliding custom groups are preserved", () => {
  const document = fixture();
  document.objects[4]!.group = "yard";
  assert.deepEqual(mergeRefinedGroups(document, previous(), refined()).migratedParts, [
    "b",
    "c",
    "d",
    "e",
  ]);
  const hidden = fixture();
  hidden.groups[0]!.hidden = true;
  hidden.groups.push({ id: "trough", name: "Custom trough", transform: identity() });
  assert.deepEqual(mergeRefinedGroups(hidden, previous(), refined()).migratedParts, []);
});

test("local asset origin changes preserve rotated authored placements and flags", async () => {
  const { rebaseLibraryRevision } = await import("./refined-map-groups.ts");
  const { transformedObstacle } = await import("@rle/shared");
  const document = fixture();
  document.objects.forEach((part) => {
    part.node = `asset:hall:${part.node}`;
  });
  document.groups[0]!.transform = { dx: 100, dy: 24, dz: 3, rot_deg: 35 };
  document.objects[0]!.transform = { dx: 2, dy: 5, dz: 1, rot_deg: 18 };
  document.objects[0]!.hidden = true;
  const expected = document.objects.map((part) => transformedObstacle(document, part));
  const revised = structuredClone(document);
  for (const part of revised.objects)
    for (const point of part.obstacle.points) {
      point.x -= 20;
      point.y -= 10 * Math.sin((35 * Math.PI) / 180);
    }
  rebaseLibraryRevision(document, revised, { hall: [100, 200, 0] }, { hall: [120, 190, 0] });
  assert.equal(document.objects[0]!.hidden, true);
  for (let i = 0; i < document.objects.length; i++) {
    const actual = transformedObstacle(document, document.objects[i]!);
    actual.points.forEach((p, j) => {
      for (const k of ["x", "y", "z_bottom", "z_top"] as const)
        assert.ok(Math.abs(p[k] - expected[i]!.points[j]![k]) < 1e-8, `${i}/${j}/${k}`);
    });
  }
});
