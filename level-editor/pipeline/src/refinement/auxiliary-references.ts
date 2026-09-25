import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import sharp from "sharp";

const sha = (bytes: Buffer) => crypto.createHash("sha256").update(bytes).digest("hex");
type Reference = {file: string; sha256: string; source: "input" | "lighting";
  crop: {left: number; top: number; width: number; height: number}; scale: number};

/** Explanatory crops may magnify approved pixels, never introduce new artwork. */
export async function auxiliaryReferences(file: string | null, input: Buffer, lighting: Buffer | null) {
  if (!file) return {images: [] as Buffer[], evidence: null, instructions: ""};
  if (!lighting) throw new Error("Auxiliary references require the calibrated lighting reference second");
  const bytes = await fs.readFile(file);
  const manifest = JSON.parse(bytes.toString()) as {
    input_sha256: string; lighting_sha256: string; references: Reference[];
  };
  if (manifest.input_sha256 !== sha(input) || manifest.lighting_sha256 !== sha(lighting))
    throw new Error("Auxiliary references do not bind the approved input and lighting");
  if (!Array.isArray(manifest.references) || !manifest.references.length || manifest.references.length > 4)
    throw new Error("Supply one to four explanatory crop references");
  const images: Buffer[] = [];
  const records = [];
  for (const reference of manifest.references) {
    if (reference.source !== "input" && reference.source !== "lighting")
      throw new Error("Auxiliary crop source must be input or lighting");
    const {left, top, width, height} = reference.crop;
    if (![left, top, width, height, reference.scale].every(Number.isInteger) ||
        left < 0 || top < 0 || width < 1 || height < 1 || reference.scale < 1 || reference.scale > 16)
      throw new Error("Invalid auxiliary crop geometry");
    const source = reference.source === "input" ? input : lighting;
    const metadata = await sharp(source).metadata();
    if (left + width > metadata.width! || top + height > metadata.height! ||
        Math.max(width, height) * reference.scale > 3840)
      throw new Error("Auxiliary crop exceeds approved source or reference size");
    const image = await fs.readFile(path.resolve(path.dirname(file), reference.file));
    if (sha(image) !== reference.sha256) throw new Error("Auxiliary reference hash changed");
    const expected = await sharp(source).extract(reference.crop)
      .resize(width * reference.scale, height * reference.scale, {kernel: "nearest"}).ensureAlpha().raw().toBuffer();
    const actual = await sharp(image).ensureAlpha().raw().toBuffer({resolveWithObject: true});
    if (actual.info.width !== width * reference.scale || actual.info.height !== height * reference.scale ||
        !actual.data.equals(expected)) throw new Error("Auxiliary reference is not an exact magnified approved crop");
    images.push(image);
    records.push({...reference, source_sha256: sha(source)});
  }
  return {images, evidence: {manifest_sha256: sha(bytes), references: records},
    instructions: " Additional references are magnified explanatory crops, not replacement views. " +
      records.map((r, i) => `Image ${i + 3} is a ${r.scale}x crop of the ${r.source === "input" ? "first" : "second"} image at full-sheet pixel box (${r.crop.left},${r.crop.top},${r.crop.width},${r.crop.height}).`).join(" ") +
      " Return only the complete first image at its original dimensions and eight-view layout."};
}
