/**
 * Internal step of `refinement/blender/lossy_assets.py`: turn one model (normally the freshly
 * derived lossy.glb) into its browser preview GLB.
 *
 *   node src/preview-model.ts <input.glb> <output.glb>   -> writes output, prints JSON
 *   node src/preview-model.ts --fingerprint               -> prints the settings/tool fingerprint
 *
 * Geometry is simplified and meshopt-compressed (the editor's preview loader registers the
 * meshopt decoder); the texture is re-encoded as AVIF at `previewTextureSize`. Reading from a
 * path lets resource-backed models resolve their shared payloads. Receipts, index fields and
 * locking belong to the caller.
 */
import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { dequantize, meshopt, simplify, textureCompress, unpartition } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptSimplifier } from "meshoptimizer";
import sharp from "sharp";

export const SETTINGS = {
  ratio: 0.12,
  error: 0.001,
  level: "high",
  targetFormat: "avif",
  quality: 45,
  texture: { divisor: 8, multiple: 16, min: 32, max: 512 },
} as const;

const digest = (bytes: string | Uint8Array) => createHash("sha256").update(bytes).digest("hex");

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

/** Settings, installed tool versions and this script: a changed fingerprint rebuilds previews. */
export async function previewFingerprint(): Promise<string> {
  const require = createRequire(import.meta.url);
  const versions: Record<string, string> = {};
  for (const name of ["@gltf-transform/core", "@gltf-transform/extensions", "@gltf-transform/functions", "meshoptimizer", "sharp"]) {
    let directory = path.dirname(require.resolve(name));
    for (;;) {
      const info = await fs.readFile(path.join(directory, "package.json"), "utf8").then(JSON.parse, () => undefined);
      if (info?.name === name) {
        versions[name] = info.version;
        break;
      }
      const parent = path.dirname(directory);
      if (parent === directory) throw new Error(`Cannot locate installed version of ${name}`);
      directory = parent;
    }
  }
  return digest(JSON.stringify({ settings: SETTINGS, versions, sharp: sharp.versions,
    script: digest(await fs.readFile(fileURLToPath(import.meta.url))) }));
}

/** Preview GLB bytes for the model at `input`, plus the texture edge used (null: untextured). */
export async function generatePreview(input: string): Promise<{ bytes: Uint8Array; edge: number | null; texels: number }> {
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ "meshopt.encoder": MeshoptEncoder });
  const document = await io.read(input);
  const texels = document.getRoot().listTextures().reduce((sum, texture) => {
    const size = texture.getSize();
    if (!size) throw new Error(`Unknown texture size: ${texture.getName()}`);
    return sum + size[0] * size[1];
  }, 0);
  const edge = texels > 0 ? previewTextureSize(texels) : null;
  const transforms = [
    // Shared-payload models read their external buffers; the preview embeds one buffer.
    unpartition(),
    // Re-quantization remaps positions through negative values; use floats so unsigned
    // source accessors cannot corrupt those intermediate coordinates.
    dequantize(),
    simplify({ simplifier: MeshoptSimplifier, ratio: SETTINGS.ratio, error: SETTINGS.error }),
    meshopt({ encoder: MeshoptEncoder, level: SETTINGS.level }),
  ];
  if (edge !== null)
    transforms.push(textureCompress({ encoder: sharp, targetFormat: SETTINGS.targetFormat, resize: [edge, edge], quality: SETTINGS.quality }));
  await document.transform(...transforms);
  return { bytes: await io.writeBinary(document), edge, texels };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [input, output] = process.argv.slice(2);
  if (input === "--fingerprint") {
    console.log(await previewFingerprint());
  } else {
    if (!input || !output) throw new Error("Usage: node src/preview-model.ts <input.glb> <output.glb> | --fingerprint");
    const { bytes, edge, texels } = await generatePreview(path.resolve(input));
    if (bytes.length === 0) throw new Error(`Empty preview: ${input}`);
    await fs.writeFile(output, bytes);
    console.log(JSON.stringify({ output, bytes: bytes.length, sha256: digest(bytes), edge, texels }));
  }
}
