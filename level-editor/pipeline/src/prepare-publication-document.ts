/** Initialize a staged editor document from reviewed export ownership and source obstacles. */
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { authoredAssetGroups, documentProvenance, IDENTITY_TRANSFORM, parseProtoLevel,
  parseSceneDoc, parseLevel3D, type AuthoredAssetCatalog, type AuthoredAssetPart,
  type Level3D, type Level3DObject } from "@rle/shared";

type Node = { name?: string; children?: number[]; extras?: Record<string, unknown> };
export function catalogFromExport(nodes: Node[], reviewed: AuthoredAssetCatalog): AuthoredAssetCatalog {
  const roots = nodes.filter(node => node.name === "map");
  if (roots.length !== 1) throw new Error("Expected exactly one map root");
  const seen = new Set<string>();
  const catalog: AuthoredAssetCatalog = { map: reviewed.map, groups: [] };
  for (const index of roots[0]!.children ?? []) {
    const group = nodes[index];
    if (!group) throw new Error("Missing export group node");
    if (group.name === "ground") continue;
    const id = group.extras?.asset_group;
    if (typeof id !== "string" || !id || !group.name) throw new Error("Missing export group identity");
    const authority = reviewed.groups.find(entry => entry.id === id);
    if (!authority || authority.name !== group.name) throw new Error("Export group differs from reviewed catalog: " + id);
    const parts: AuthoredAssetPart[] = [];
    for (const child of group.children ?? []) {
      const part = nodes[child], name = part?.name, extras = part?.extras;
      if (!name || seen.has(name)) throw new Error("Missing or duplicated export part");
      seen.add(name);
      const match = /^(building|terrace)-(\d+)$/.exec(name);
      const expected = authority.parts.find(entry => match ? entry.obstacle === Number(match[2]) : entry.node === name);
      if (!expected || extras?.part_name !== expected.name) throw new Error("Export part differs from reviewed ownership: " + name);
      if (match) {
        if (extras?.source_obstacle !== Number(match[2])) throw new Error("Export obstacle identity mismatch: " + name);
        parts.push({ obstacle: Number(match[2]), name: expected.name });
      } else {
        if (!/^mission-[a-zA-Z0-9_-]+$/.test(name) || expected.mission_profile !== extras?.mission_patch_profile ||
            !extras?.obstacle_local_game || extras.source_obstacle !== undefined)
          throw new Error("Invalid supplemental mission metadata: " + name);
        parts.push({ node: name, name: expected.name, mission_profile: expected.mission_profile!,
          obstacle_local_game: extras.obstacle_local_game as NonNullable<AuthoredAssetPart["obstacle_local_game"]> });
      }
    }
    if (parts.length !== authority.parts.length) throw new Error("Missing reviewed group parts: " + id);
    catalog.groups.push({ id, name: authority.name, parts });
  }
  if (catalog.groups.length !== reviewed.groups.length || new Set(catalog.groups.map(group => group.id)).size !== reviewed.groups.length)
    throw new Error("Export group coverage differs from reviewed catalog");
  return catalog;
}

export async function prepareDocument(scenePath: string, levelPath: string, glbPath: string, catalogPath: string, output: string) {
  const scene = parseSceneDoc(JSON.parse(await readFile(scenePath, "utf8")));
  const level = parseProtoLevel(JSON.parse(await readFile(levelPath, "utf8")));
  const bytes = await readFile(glbPath);
  if (bytes.toString("ascii", 0, 4) !== "glTF" || bytes.readUInt32LE(16) !== 0x4e4f534a) throw new Error("Expected GLB JSON chunk");
  const model = JSON.parse(bytes.toString("utf8", 20, 20 + bytes.readUInt32LE(12))) as { nodes: Node[] };
  const reviewed = JSON.parse(await readFile(catalogPath, "utf8")) as AuthoredAssetCatalog;
  if (reviewed.map.toLowerCase() !== scene.map.toLowerCase()) throw new Error("Catalog map mismatch");
  const catalog = catalogFromExport(model.nodes, reviewed);
  const objects: Level3DObject[] = [];
  for (const group of catalog.groups) for (const part of group.parts) {
    if (part.mission_profile !== undefined) {
      objects.push({ id: part.node, node: part.node, kind: "mission", name: part.name,
        source: { map: scene.map, mission_profile: part.mission_profile },
        obstacle: structuredClone(part.obstacle_local_game!), transform: { ...IDENTITY_TRANSFORM } });
    } else {
      const node = model.nodes.find(node => node.extras?.source_obstacle === part.obstacle && /^(building|terrace)-\d+$/.test(node.name ?? ""))!;
      const obstacle = level.sight_obstacles[part.obstacle];
      if (!obstacle) throw new Error("Missing source obstacle " + part.obstacle);
      objects.push({ id: node.name!, node: node.name!, kind: node.name!.startsWith("terrace-") ? "terrace" : "building",
        source: { map: scene.map, obstacle: part.obstacle }, obstacle, transform: { ...IDENTITY_TRANSFORM } });
    }
  }
  const groups = authoredAssetGroups(scene.map, objects, catalog)!;
  const provenance = await documentProvenance(level, bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer);
  const document: Level3D = { version: 1, map: scene.map, size: scene.size, camera: scene.camera,
    glb: scene.map.toLowerCase() + "-volumes.scene.glb", groups, objects, provenance };
  parseLevel3D(document, { scene, level, nodes: new Set(objects.map(object => object.node)),
    sourceSha256: provenance.source_sha256, glbSha256: provenance.glb_sha256 });
  await writeFile(output, JSON.stringify(document, null, 2) + "\n", { flag: "wx" });
  return { file: output, groups: groups.length, parts: objects.length, provenance };
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const args = process.argv.slice(2);
  if (args.length !== 5) throw new Error("Usage: prepare-publication-document.ts scene.json level.json staged.glb reviewed-catalog.json new.level3d.json");
  console.log(JSON.stringify(await prepareDocument(...args.map(arg => resolve(arg)) as [string, string, string, string, string])));
}
