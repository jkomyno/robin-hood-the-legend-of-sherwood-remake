/** Convert a published reconstruction into a JSON manifest and byte-preserving assets. */
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHash } from "node:crypto";
import {
  groupObstacles,
  parseStoredMap,
  IDENTITY_TRANSFORM,
  parseLevel3D,
  parseProtoLevel,
  parseSceneDoc,
  type Level3D,
  type Level3DObject,
  type ProtoLevel,
  type SceneDoc,
  type SceneAssetSource,
} from "@rle/shared";
import { pinnedDescriptors } from "./stored-map.ts";

const execute = promisify(execFile);
const hash = (data: string | Buffer) => createHash("sha256").update(data).digest("hex");
export function initializeSceneDocument(
  scene: SceneDoc,
  level: ProtoLevel,
  names: string[],
): Level3D {
  const objects: Level3DObject[] = names
    .sort()
    .filter((name) => /^(building|terrace)-\d+$/.test(name))
    .map((node) => {
      const [kind, value] = node.split("-");
      const obstacle = Number(value);
      if (!level.sight_obstacles[obstacle]) throw new Error(`Missing source obstacle ${obstacle}`);
      return {
        id: node,
        kind: kind as "building" | "terrace",
        node,
        source: { map: scene.map, obstacle },
        obstacle: level.sight_obstacles[obstacle],
        transform: { ...IDENTITY_TRANSFORM },
      };
    });
  const terraces = new Set(
    objects.filter((part) => part.kind === "terrace").map((part) => part.source.obstacle!),
  );
  const grouping = groupObstacles(level.sight_obstacles, terraces);
  const groups: Level3D["groups"] = [];
  for (const object of objects) {
    const root = grouping.get(object.source.obstacle!);
    if (root === undefined) continue;
    object.group = `group-${String(root).padStart(3, "0")}`;
    if (!groups.some((group) => group.id === object.group))
      groups.push({ id: object.group, transform: { ...IDENTITY_TRANSFORM } });
  }
  return {
    version: 1,
    map: scene.map,
    size: scene.size,
    camera: scene.camera,
    sourceMap: scene.map,
    sceneAssets: [],
    objects,
    groups,
  };
}

export async function importScene(
  glb: string,
  outputLibrary: string,
  document: Record<string, unknown>,
  sourceMap?: string,
) {
  if (
    document.version === 2 ||
    (Array.isArray(document.objects) &&
      document.objects.some(
        (object: any) =>
          object?.node?.startsWith("asset:") &&
          (object.obstacle === undefined ||
            object.source === undefined ||
            object.kind === undefined ||
            object.transform === undefined),
      ))
  )
    document = parseStoredMap(
      document,
      await pinnedDescriptors(
        outputLibrary,
        (document.assetSources ?? []) as import("@rle/shared").ExternalAssetSource[],
      ),
    ) as unknown as Record<string, unknown>;
  const reportFile = path.join(outputLibrary, "import-reports", `${String(document.map)}.json`);
  await execute(
    "python3",
    [
      fileURLToPath(new URL("../split_scene_assets.py", import.meta.url)),
      glb,
      outputLibrary,
      "--report",
      reportFile,
    ],
    { maxBuffer: 1024 * 1024 },
  );
  const report = JSON.parse(await fs.readFile(reportFile, "utf8")) as {
    sceneAssets: SceneAssetSource[];
    files: Record<string, string>;
    source_sha256: string;
    verified_assets: number;
  };
  const { glb: _glb, ...rest } = document;
  const previous = rest.provenance as Record<string, unknown> | undefined;
  const { glb_sha256: _sha, ...provenance } = previous ?? {};
  const result = parseLevel3D({
    ...rest,
    provenance: Object.keys(provenance).length ? provenance : undefined,
    sourceMap,
    sceneAssets: report.sceneAssets,
  });
  return { document: result, report };
}

async function main() {
  const { parseArgs } = await import("node:util");
  const { values } = parseArgs({
    options: {
      library: { type: "string" },
      output: { type: "string" },
      datadir: { type: "string" },
      map: { type: "string" },
    },
  });
  if (!values.library || !values.output || !values.datadir)
    throw new Error(
      "Usage: --library directory --output staging-directory --datadir directory [--map name]",
    );
  const library = path.resolve(values.library),
    output = path.resolve(values.output);
  if (library === output) throw new Error("Use a separate staging library");
  const sceneDir = path.join(library, "scenes");
  const files = await fs.readdir(sceneDir);
  const reports = [];
  for (const filename of files.filter((name) => name.endsWith("-volumes.scene.glb")).sort()) {
    const name = filename.slice(0, -"-volumes.scene.glb".length);
    if (values.map && name !== values.map) continue;
    const source = path.join(sceneDir, filename);
    const metadataFile = path.join(sceneDir, `${name}-volumes.scene.json`);
    const metadataBytes = await fs.readFile(metadataFile);
    const scene = parseSceneDoc(JSON.parse(metadataBytes.toString()));
    const documentFile = path.join(sceneDir, `${name}.rhlos-map.json`);
    const previous = files.includes(`${name}.rhlos-map.json`)
      ? await fs.readFile(documentFile)
      : null;
    let document: Record<string, unknown>;
    if (previous) document = JSON.parse(previous.toString());
    else {
      const level = parseProtoLevel(
        JSON.parse(
          await fs.readFile(
            path.join(values.datadir, "Data", "Levels", `${scene.map}.rhp.json`),
            "utf8",
          ),
        ),
      );
      const bytes = await fs.readFile(source);
      const gltf = JSON.parse(bytes.toString("utf8", 20, 20 + bytes.readUInt32LE(12)));
      document = initializeSceneDocument(
        scene,
        level,
        gltf.nodes.map((node: { name: string }) => node.name),
      ) as unknown as Record<string, unknown>;
      document.provenance = { source_sha256: hash(JSON.stringify(level)) };
    }
    const converted = await importScene(
      source,
      output,
      document,
      scene.standalone ? undefined : scene.map,
    );
    if (
      hash(await fs.readFile(source)) !== converted.report.source_sha256 ||
      hash(await fs.readFile(metadataFile)) !== hash(metadataBytes) ||
      (previous && hash(await fs.readFile(documentFile)) !== hash(previous))
    )
      throw new Error(`Source changed during import: ${name}`);
    await fs.mkdir(path.join(output, "scenes"), { recursive: true });
    await fs.writeFile(
      path.join(output, "scenes", `${name}.rhlos-map.json`),
      JSON.stringify(converted.document, null, 2) + "\n",
    );
    reports.push({
      name,
      glb: source,
      glb_sha256: converted.report.source_sha256,
      metadata: metadataFile,
      metadata_sha256: hash(metadataBytes),
      document: documentFile,
      previous_document_sha256: previous ? hash(previous) : null,
      objects: converted.document.objects.length,
      groups: converted.document.groups.length,
      assets: converted.report.verified_assets,
    });
    console.log(
      `${name}: ${converted.report.verified_assets} exact assets; ${converted.document.objects.length} unchanged parts`,
    );
  }
  await fs.writeFile(
    path.join(output, "migration.json"),
    JSON.stringify({ library, output, maps: reports }, null, 2) + "\n",
  );
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href)
  main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
