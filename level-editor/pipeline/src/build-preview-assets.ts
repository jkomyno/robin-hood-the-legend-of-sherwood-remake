/**
 * Build lightweight browser-only GLBs: `pnpm --filter pipeline build-previews`.
 * An optional positional argument selects another library root. Each preview has
 * a .receipt.json binding its bytes to source SHA-256, settings, installed tool
 * versions and this script. Missing/invalid receipts or outputs are rebuilt;
 * existing previews without receipts rebuild once. Assets are processed serially.
 * Linux `flock` shares the publisher lock while merging the latest library index.
 *
 * The source is the entry's `lossy_model` while its receipt binds it to the current
 * `model` bytes (self-contained, already re-baked to one atlas), otherwise `model`.
 * The preview texture edge follows the source texels: see `previewTextureSize`.
 */
import fs from "node:fs/promises";
import path from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { meshopt, simplify, textureCompress } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptSimplifier } from "meshoptimizer";
import sharp from "sharp";

const SETTINGS = {
  ratio: 0.12,
  error: 0.015,
  level: "high",
  targetFormat: "avif",
  quality: 45,
  texture: { divisor: 8, multiple: 16, min: 32, max: 512 },
} as const;

/**
 * Preview texture edge for a source whose images hold `texels` in total: the edge of the
 * equivalent square atlas divided by `divisor`, rounded up to `multiple`, clamped to [min, max].
 * Lossy atlases hold ~1 texel per map pixel, so this is ~1 texel per `divisor` map pixels.
 */
export function previewTextureSize(
  texels: number,
  rule: { divisor: number; multiple: number; min: number; max: number } = SETTINGS.texture,
): number {
  if (!(texels > 0)) throw new Error("Preview source has no texture texels");
  const edge = Math.ceil(Math.sqrt(texels) / rule.divisor / rule.multiple) * rule.multiple;
  return Math.min(rule.max, Math.max(rule.min, edge));
}
const digest = (bytes: string | Uint8Array) => createHash("sha256").update(bytes).digest("hex");
type Index = { version: number; assets: Array<Record<string, unknown>> };
type Receipt = { source: string; fingerprint: string; output: string; source_model?: string };

/** The lossy model when its receipt binds it to the current model bytes, else the model. */
async function previewSource(
  root: string,
  entry: Record<string, unknown>,
  log?: (message: string) => void,
): Promise<string> {
  const model = String(entry.model);
  if (entry.lossy_model === undefined) return model;
  const lossy = String(entry.lossy_model);
  const receiptBytes = await readOptional(path.join(root, `${lossy}.receipt.json`));
  const lossyBytes = await readOptional(path.join(root, lossy));
  if (!receiptBytes || !lossyBytes)
    throw new Error(`Indexed lossy model or receipt is missing: ${lossy}`);
  const receipt = JSON.parse(receiptBytes.toString()) as { source?: unknown; output?: unknown };
  if (receipt.output !== digest(lossyBytes))
    throw new Error(`Lossy model does not match its receipt: ${lossy}`);
  if (receipt.source !== digest(await fs.readFile(path.join(root, model)))) {
    log?.(`${String(entry.id)}: lossy model is stale; previewing ${model}`);
    return model;
  }
  return lossy;
}

async function readOptional(file: string): Promise<Buffer | undefined> {
  try {
    return await fs.readFile(file);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw error;
  }
}

/** Same advisory lock as the library publisher; closing stdin releases it. */
async function withLibraryLock<T>(root: string, action: () => Promise<T>): Promise<T> {
  const child = spawn(
    "flock",
    [
      "--exclusive",
      path.join(root, ".publication.lock"),
      process.execPath,
      "-e",
      'process.stdout.write("locked\\n"); process.stdin.resume();',
    ],
    { stdio: ["pipe", "pipe", "inherit"] },
  );
  const exited = new Promise<void>((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(`Library lock exited ${code}`)),
    );
  });
  // Attach a rejection handler immediately, including while waiting for acquisition.
  void exited.catch(() => {});
  await Promise.race([
    new Promise<void>((resolve) => child.stdout.once("data", () => resolve())),
    exited.then(() => {
      throw new Error("Library lock exited before acquisition");
    }),
  ]);
  try {
    return await action();
  } finally {
    child.stdin.end();
    await exited;
  }
}

async function atomicWrite(file: string, bytes: string | Uint8Array): Promise<void> {
  const temporary = `${file}.${randomUUID()}.tmp`;
  try {
    await fs.writeFile(temporary, bytes);
    await fs.rename(temporary, file);
  } finally {
    await fs.rm(temporary, { force: true });
  }
}

export async function buildPreviews(
  root: string,
  options: {
    fingerprint: string;
    generate: (source: Uint8Array) => Promise<Uint8Array>;
    log?: (message: string) => void;
  },
): Promise<{ generated: number; skipped: number }> {
  const indexPath = path.join(root, "index.json");
  const initial = JSON.parse(await fs.readFile(indexPath, "utf8")) as Index;
  let generated = 0,
    skipped = 0;
  for (const entry of initial.assets) {
    const id = String(entry.id),
      model = String(entry.model);
    if (!/^[a-zA-Z0-9_-]+$/.test(id)) throw new Error(`Invalid asset ID: ${id}`);
    const sourceModel = await previewSource(root, entry, options.log);
    const source = path.resolve(root, sourceModel);
    if (!source.startsWith(path.resolve(root) + path.sep))
      throw new Error(`Model outside library: ${sourceModel}`);
    const previewModel = path.posix.join(path.posix.dirname(model), "preview.glb"),
      preview = path.join(root, previewModel);
    const receiptPath = `${preview}.receipt.json`;
    const sourceBytes = await fs.readFile(source),
      sourceHash = digest(sourceBytes);
    const previousOutput = await readOptional(preview);
    const receiptBytes = await readOptional(receiptPath);
    let receipt: Receipt | undefined;
    try {
      receipt = receiptBytes && JSON.parse(receiptBytes.toString());
    } catch {
      /* Invalid receipt is stale. */
    }
    const fresh =
      previousOutput &&
      previousOutput.length > 0 &&
      receipt?.source === sourceHash &&
      receipt.source_model === sourceModel &&
      receipt.fingerprint === options.fingerprint &&
      receipt.output === digest(previousOutput);
    const output = fresh ? previousOutput : await options.generate(sourceBytes);
    if (output.length === 0) throw new Error(`Empty preview: ${id}`);
    await withLibraryLock(root, async () => {
      // Generation happens outside the lock; merge only against current library contents.
      const current = JSON.parse(await fs.readFile(indexPath, "utf8")) as Index;
      const currentEntry = current.assets.find((candidate) => candidate.id === id);
      if (
        !currentEntry ||
        currentEntry.model !== model ||
        (currentEntry.lossy_model ?? model) !== (entry.lossy_model ?? model) ||
        digest(await fs.readFile(source)) !== sourceHash
      ) {
        throw new Error(
          `Asset changed during preview generation: ${id}; rerun to use the latest source`,
        );
      }
      await fs.mkdir(path.dirname(preview), { recursive: true });
      const livePreview = await readOptional(preview);
      const liveReceipt = await readOptional(receiptPath);
      if (
        !fresh ||
        !livePreview ||
        digest(livePreview) !== digest(output) ||
        !liveReceipt?.equals(receiptBytes!)
      ) {
        await atomicWrite(preview, output);
        await atomicWrite(
          receiptPath,
          JSON.stringify({
            source: sourceHash,
            source_model: sourceModel,
            fingerprint: options.fingerprint,
            output: digest(output),
          }) + "\n",
        );
      }
      if (currentEntry.preview_model !== previewModel) {
        currentEntry.preview_model = previewModel;
        await atomicWrite(indexPath, JSON.stringify(current, null, 2) + "\n");
      }
    });
    if (fresh) skipped++;
    else generated++;
    options.log?.(
      `${id}: ${fresh ? "up to date" : `${sourceModel} ${(sourceBytes.length / 1048576).toFixed(2)} MB -> ${(output.length / 1048576).toFixed(3)} MB`}`,
    );
  }
  return { generated, skipped };
}

async function toolFingerprint(): Promise<string> {
  const require = createRequire(import.meta.url);
  const versions: Record<string, string> = {};
  for (const name of [
    "@gltf-transform/core",
    "@gltf-transform/extensions",
    "@gltf-transform/functions",
    "meshoptimizer",
    "sharp",
  ]) {
    let directory = path.dirname(require.resolve(name));
    for (;;) {
      const bytes = await readOptional(path.join(directory, "package.json"));
      const info = bytes && JSON.parse(bytes.toString());
      if (info?.name === name) {
        versions[name] = info.version;
        break;
      }
      const parent = path.dirname(directory);
      if (parent === directory) throw new Error(`Cannot locate installed version of ${name}`);
      directory = parent;
    }
  }
  return digest(
    JSON.stringify({
      settings: SETTINGS,
      versions,
      sharp: sharp.versions,
      script: digest(await fs.readFile(fileURLToPath(import.meta.url))),
    }),
  );
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = path.resolve(process.argv[2] ?? "../library/3d-assets");
  const io = new NodeIO()
    .registerExtensions(ALL_EXTENSIONS)
    .registerDependencies({ "meshopt.encoder": MeshoptEncoder });
  const result = await buildPreviews(root, {
    fingerprint: await toolFingerprint(),
    log: console.log,
    generate: async (source) => {
      // Read the hashed bytes, so the build cannot silently use a newer source revision.
      const document = await io.readBinary(source);
      const texels = document
        .getRoot()
        .listTextures()
        .reduce((sum, texture) => {
          const size = texture.getSize();
          if (!size) throw new Error(`Unknown texture size: ${texture.getName()}`);
          return sum + size[0] * size[1];
        }, 0);
      const transforms = [
        simplify({ simplifier: MeshoptSimplifier, ratio: SETTINGS.ratio, error: SETTINGS.error }),
        meshopt({ encoder: MeshoptEncoder, level: SETTINGS.level }),
      ];
      if (texels > 0) {
        const edge = previewTextureSize(texels);
        transforms.push(
          textureCompress({
            encoder: sharp,
            targetFormat: SETTINGS.targetFormat,
            resize: [edge, edge],
            quality: SETTINGS.quality,
          }),
        );
      }
      await document.transform(...transforms);
      return await io.writeBinary(document);
    },
  });
  console.log(`Previews: ${result.generated} generated, ${result.skipped} up to date.`);
}
