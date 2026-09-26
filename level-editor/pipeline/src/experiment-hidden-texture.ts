/** Controlled, explicitly requested hidden-face Images API experiment. */
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import sharp from "sharp";
import { requireEnv } from "./env.ts";

const MODEL = "gpt-image-2.5-sunburst";
const ENDPOINT = "https://api.openai.com/v1/images/edits";

async function main(): Promise<void> {
  const directory = path.resolve(process.argv[2] ?? "");
  if (!process.argv[2]) throw new Error("Supply prepared experiment directory");
  if (process.argv.includes("--verify-renders")) {
    const comparisons: Record<string, number> = {};
    for (const view of ["source", "rear"]) {
      const [before, after] = await Promise.all(
        ["before", "after"].map(async (stage) =>
          sharp(path.join(directory, stage, `${view}-textured.png`))
            .ensureAlpha()
            .raw()
            .toBuffer(),
        ),
      );
      if (!before || !after || before.length !== after.length)
        throw new Error("Mismatched comparison renders");
      let changed = 0;
      for (let i = 0; i < before.length; i += 4)
        if (
          before[i] !== after[i] ||
          before[i + 1] !== after[i + 1] ||
          before[i + 2] !== after[i + 2] ||
          before[i + 3] !== after[i + 3]
        )
          changed++;
      comparisons[`${view}ChangedPixels`] = changed;
    }
    await fs.writeFile(
      path.join(directory, "render-verification.json"),
      JSON.stringify(comparisons, null, 2),
    );
    console.log(JSON.stringify(comparisons, null, 2));
    if (comparisons.sourceChangedPixels !== 0)
      throw new Error("Source artwork changed in the experiment");
    if (!comparisons.rearChangedPixels)
      throw new Error("Generated concealed texture is not visible in comparison");
    return;
  }
  const names = ["tile.png", "mask.png", "context.png"];
  const refinement = process.argv.includes("--refine");
  const wholeBuilding = process.argv.includes("--whole-building");
  const [tile, mask, context] = await Promise.all(
    names.map((n) => fs.readFile(path.join(directory, n))),
  );
  if (!tile || !mask || !context) throw new Error("Missing prepared images");
  const sourceFull = refinement ? await fs.readFile(path.join(directory, "source-full.png")) : null;
  const parameters = {
    model: MODEL,
    size: "1024x1024",
    n: "1",
    output_format: "png",
    prompt:
      "Complete only the transparent interior of this triangular medieval conical roof texture. Preserve the opaque border exactly. Continue the same small weathered brown clay shingles, painterly grain, muted colors, and shingle size. The second image is the source gatehouse for style and architectural context. Paint only roof shingles; no windows, masonry, text, objects, or changes to the triangle silhouette. The texture will be applied only to one concealed rear roof face; the original visible artwork is protected separately.",
  };
  if (refinement)
    parameters.prompt =
      "Repair only the transparent central patch in image 1. Image 2 shows the gatehouse and image 3 is the EXACT original complete UV tile, giving precise shingle size, row curvature, orientation, lighting, and color. Continue every row entering the transparent patch at exactly its existing position and pitch. Match the original tiny rounded irregular scalloped shingles: do not straighten courses, enlarge shingles, change row spacing, substitute rectangular overlapping slates, smooth the grain, or add dramatic highlights. This is a small concealed conical roof face, not a photograph or a new design. The prior attempt made shingles too large and straight and caused a seam; correct those specific errors. Match image 3 pixel scale throughout the filled area and leave the opaque border exactly unchanged.";
  if (wholeBuilding)
    parameters.prompt =
      "Image 1 is an exact untextured 3D REAR structural render of a medieval gatehouse. Image 2 is the textured FRONT of the SAME building. Paint the rear building in image 1 using the same weathered grey-brown stone blockwork, small rounded reddish brown roof shingles, aged metal roof caps, and fine painterly pixel grain seen in image 2. Crucially preserve image 1's exact silhouette, camera, perspective, tower sizes, roof peaks and eaves, central roof, wall edges, arch opening, every structural boundary and background. Do not copy the front viewpoint. Do not shift, redesign, add or remove any geometry, windows, doors, towers, people, props, text, or shadows outside the silhouette. Continue stone courses and roof shingles naturally around the back at precisely the same physical scale and color as the front. Do not add large smooth surfaces or oversized roof tiles. Return the identical rear view with only its existing grey building surfaces painted. Background and arch void remain untouched.";
  const digest = crypto
    .createHash("sha256")
    .update(JSON.stringify(parameters))
    .update(tile)
    .update(mask)
    .update(context)
    .update(sourceFull ?? Buffer.alloc(0))
    .digest("hex");
  const cache = path.join(directory, "api-cache", digest);
  await fs.mkdir(cache, { recursive: true });
  await fs.writeFile(
    path.join(cache, "request.json"),
    JSON.stringify(
      {
        endpoint: ENDPOINT,
        parameters,
        images: sourceFull ? [...names, "source-full.png"] : names,
        sha256: digest,
      },
      null,
      2,
    ),
  );
  if (sourceFull) await fs.writeFile(path.join(cache, "source-full.png"), sourceFull);
  for (const [i, bytes] of [tile, mask, context].entries())
    await fs.writeFile(path.join(cache, names[i]!), bytes);
  const responsePath = path.join(cache, "response.json");
  let response: { status: number; body: unknown };
  try {
    response = JSON.parse(await fs.readFile(responsePath, "utf8"));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    const form = new FormData();
    for (const [name, value] of Object.entries(parameters)) form.append(name, value);
    form.append("image[]", new Blob([new Uint8Array(tile)], { type: "image/png" }), "tile.png");
    form.append(
      "image[]",
      new Blob([new Uint8Array(context)], { type: "image/png" }),
      "context.png",
    );
    if (sourceFull)
      form.append(
        "image[]",
        new Blob([new Uint8Array(sourceFull)], { type: "image/png" }),
        "source-full.png",
      );
    form.append("mask", new Blob([new Uint8Array(mask)], { type: "image/png" }), "mask.png");
    const raw = await fetch(ENDPOINT, {
      method: "POST",
      headers: { Authorization: `Bearer ${requireEnv("OPENAI_API_KEY")}` },
      body: form,
    });
    const text = await raw.text();
    let body: unknown;
    try {
      body = JSON.parse(text);
    } catch {
      body = { text };
    }
    response = { status: raw.status, body };
    await fs.writeFile(responsePath, JSON.stringify(response, null, 2));
  }
  if (response.status < 200 || response.status >= 300) {
    console.log(
      JSON.stringify(
        { model: MODEL, status: response.status, error: response.body, cache },
        null,
        2,
      ),
    );
    process.exitCode = 1;
    return;
  }
  const body = response.body as { data?: { b64_json?: string }[] };
  const encoded = body.data?.[0]?.b64_json;
  if (!encoded) throw new Error("Successful response did not contain image bytes");
  const generated = Buffer.from(encoded, "base64");
  await fs.writeFile(path.join(cache, "generated.png"), generated);
  const { data: original, info } = await sharp(tile)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  const pixels = await sharp(generated)
    .resize(info.width, info.height)
    .ensureAlpha()
    .raw()
    .toBuffer();
  const editMask = wholeBuilding ? await sharp(mask).ensureAlpha().raw().toBuffer() : original;
  const result = Buffer.from(original);
  const prior = sourceFull ? await sharp(sourceFull).ensureAlpha().raw().toBuffer() : null;
  let replaced = 0;
  for (let i = 0; i < result.length; i += 4)
    if (editMask[i + 3] === 0) {
      if (prior) {
        const pixel = i / 4,
          x = pixel % info.width,
          y = Math.floor(pixel / info.width);
        let distance = 8;
        for (let dy = -8; dy <= 8; dy++)
          for (let dx = -8; dx <= 8; dx++) {
            const nx = x + dx,
              ny = y + dy;
            if (
              nx >= 0 &&
              ny >= 0 &&
              nx < info.width &&
              ny < info.height &&
              original[(ny * info.width + nx) * 4 + 3]! > 0
            )
              distance = Math.min(distance, Math.hypot(dx, dy));
          }
        const blend = Math.min(1, distance / 8);
        for (let channel = 0; channel < 3; channel++)
          result[i + channel] = Math.round(
            prior[i + channel]! * (1 - blend) + pixels[i + channel]! * blend,
          );
      } else pixels.copy(result, i, i, i + 4);
      result[i + 3] = 255;
      replaced++;
    }
  await sharp(result, { raw: { width: info.width, height: info.height, channels: 4 } })
    .png()
    .toFile(path.join(directory, "completed.png"));
  console.log(
    JSON.stringify(
      { model: MODEL, status: response.status, protectedPixelsChanged: 0, replaced, cache },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
