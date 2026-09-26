import { loadSceneModel } from "./scene-assets.ts";
import { importScene } from "./import-scene.ts";
import { compactStoredMap, readStoredMap } from "./stored-map.ts";
/** Generate terrain from the saved layout and game-art references via OpenRouter. */
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import sharp from "sharp";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { splineCurve } from "../../app/src/spline-geometry.ts";
import { libraryDir, repoRoot, workDir, loadEnvironment, requireEnv } from "./env.ts";
import {
  openRouterBody,
  providerIdentity,
  validateOpenRouterCapabilities,
} from "./refinement/image-provider.ts";

loadEnvironment();
const scenePath = path.join(libraryDir, "scenes/Wychford.rhlos-map.json");
const scene = await readStoredMap(scenePath, libraryDir);
const out = path.join(workDir, "wychford/ground-generation");
await fs.mkdir(out, { recursive: true });
const sin = Math.sin((scene.camera.elevation_deg * Math.PI) / 180);
if (!scene.size) throw new Error("Ground image generation requires compiled map bounds");
const width = scene.size[0],
  height = scene.size[1] / sin;
const points = (id: string) => {
  const spline = scene.splines!.find((s) => s.id === id)!;
  return splineCurve(spline, scene.camera)
    .getPoints(160)
    .map((p) => `${p.x.toFixed(2)},${(-p.y).toFixed(2)}`)
    .join(" ");
};
const roads = scene
  .splines!.filter((s) => s.kind === "road")
  .map(
    (s) =>
      `<polyline points="${points(s.id)}" fill="none" stroke="#b2986b" stroke-width="${s.width}" stroke-linecap="round" stroke-linejoin="round"/>`,
  )
  .join("\n");
const river = scene.splines!.find((s) => s.kind === "river")!;
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="2048" height="2048" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
<rect width="${width}" height="${height}" fill="#687245"/>
<path d="M0 0H3600V400Q3150 320 2900 150Q2200 60 2000 280Q1000 230 350 500V3700L0 4184Z" fill="#424e32"/>
<ellipse cx="2720" cy="${820 / sin}" rx="760" ry="${900 / sin}" fill="#87816a"/>
<ellipse cx="1040" cy="${1600 / sin}" rx="600" ry="${520 / sin}" fill="#8c8261"/>
${roads}
<polyline points="${points(river.id)}" fill="none" stroke="#9e9271" stroke-width="${river.width + 70}" stroke-linejoin="round"/>
<polyline points="${points(river.id)}" fill="none" stroke="#465951" stroke-width="${river.width}" stroke-linejoin="round"/>
</svg>`;
await fs.writeFile(path.join(out, "layout.svg"), svg);
const drawing = await sharp(Buffer.from(svg)).png().toBuffer();
await fs.writeFile(path.join(out, "layout.png"), drawing);
const references = [
  {
    file: "Robin's Godfather.png",
    description: "original game: grass, banks, olive water, pale rocks and worn dirt",
    image: await sharp(path.join(repoRoot, "mission-maps/Robin's Godfather.png"))
      .resize({ width: 2048 })
      .png()
      .toBuffer(),
  },
  {
    file: "Sherwood Forest.png",
    description: "original game: grass blades, rock surfaces and woodland ground",
    image: await sharp(path.join(repoRoot, "mission-maps/Sherwood Forest.png"))
      .extract({ left: 960, top: 460, width: 960, height: 628 })
      .png()
      .toBuffer(),
  },
];
for (const [i, ref] of references.entries())
  await fs.writeFile(path.join(out, `reference-${i + 1}.png`), ref.image);
const prompt = `Create a high resolution ground-only texture for an existing medieval game scene. Reference image 1 is the STRICT spatial layout guide. Its entire rectangle corresponds to the entire output: preserve the river centerline and width, bank positions and the exact road layout. Dark olive marks woodland ground at the margins, muted olive marks grass, gray marks a rocky stronghold plateau on the RIGHT, warm brown marks the market/village clearings on the LEFT, tan lines mark footpaths, and blue-gray marks the narrow river. Convert every flat color into richly detailed natural ground. Do not reproduce flat diagram colors or diagram strokes.
References 2 and 3 are from the original game and supply ONLY the visual style and material appearance: lush varied short olive grass, pale weathered limestone embedded in soil, brown worn earth paths, mossy damp riverbanks, tiny pebbles and muddy olive water. Match their natural fine detail and subdued rich colors. Do not copy their buildings, trees, cliffs, characters, shadows, camera angle or composition.
CRITICAL: The output is a perfectly flat TOP-DOWN ORTHOGRAPHIC diffuse ground texture, not an isometric painting. All depth and elevation is provided later by actual 3D geometry. No horizon, perspective, cliff faces, cast shadows, 3D-looking rocks, buildings, bridges, fences, props, labels, people or tree canopies. Surface gravel, low embedded stones, moss and leaf litter are welcome, but no raised objects. Even soft daylight. Keep clearings and paths visually calm enough for characters to read against them. Avoid pervasive gravel everywhere; most grass should be fine natural turf. Paths blend irregularly into surrounding grass, while following the guide. River banks are narrow damp strips, not huge cliffs. The water channel is dark muddy olive with subtle fine ripples. Preserve the exact river shape through the image, including its entry and exit at the top and bottom edges. Fill the entire canvas with continuous terrain and deliver only the finished ground texture. Generate true native detail at 2560 by 2560 pixels, without blurred enlargement or repeating tiles.`;
const identity = providerIdentity("openrouter");
const parameters = {
  model: identity.model,
  quality: "high",
  size: "2560x2560",
  n: "1",
  output_format: "png",
  prompt,
};
const hash = crypto.createHash("sha256").update(drawing).update(JSON.stringify(parameters));
for (const ref of references) hash.update(ref.image);
const cache = path.join(out, hash.digest("hex"));
await fs.mkdir(cache, { recursive: true });
await fs.writeFile(
  path.join(cache, "request.json"),
  JSON.stringify(
    {
      provider: identity.provider,
      endpoint: identity.endpoint,
      parameters,
      references: references.map((r) => ({
        file: r.file,
        description: r.description,
        sha256: crypto.createHash("sha256").update(r.image).digest("hex"),
      })),
    },
    null,
    2,
  ),
);
const resultPath = path.join(cache, "terrain.png");
const baseIndex = process.argv.indexOf("--base");
if (baseIndex >= 0) {
  const base = process.argv[baseIndex + 1];
  if (!base) throw new Error("--base requires a PNG path");
  await fs.copyFile(path.resolve(base), resultPath);
}
let finalPath = resultPath;
let finalSize = 2560;
if (process.argv.includes("--generate")) {
  let exists = true;
  try {
    await fs.access(resultPath);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    exists = false;
  }
  if (!exists) {
    const headers = {
      Authorization: `Bearer ${requireEnv(identity.credential)}`,
      "Content-Type": "application/json",
    };
    const capabilities = await fetch(`${identity.endpoint}/models/${identity.model}/endpoints`, {
      headers,
    });
    if (!capabilities.ok) throw new Error(`Capability discovery failed: ${capabilities.status}`);
    const metadata = await capabilities.json();
    validateOpenRouterCapabilities(metadata, 3);
    await fs.writeFile(path.join(cache, "capabilities.json"), JSON.stringify(metadata, null, 2));
    console.log(
      "Generating",
      identity.model,
      parameters.size,
      "with layout and two original-game references",
    );
    const response = await fetch(identity.endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify(
        openRouterBody(
          parameters,
          drawing,
          null,
          true,
          references.map((r) => r.image),
        ),
      ),
      signal: AbortSignal.timeout(600000),
    });
    const body = (await response.json()) as {
      data?: { b64_json?: string }[];
      usage?: unknown;
      error?: unknown;
    };
    await fs.writeFile(
      path.join(cache, "response-metadata.json"),
      JSON.stringify({ status: response.status, usage: body.usage, error: body.error }, null, 2),
    );
    if (!response.ok || !body.data?.[0]?.b64_json)
      throw new Error(
        `Image generation failed (${response.status}): ${JSON.stringify(body.error)}`,
      );
    const image = Buffer.from(body.data[0].b64_json, "base64");
    const info = await sharp(image).metadata();
    await fs.writeFile(resultPath, image);
    console.log(
      JSON.stringify({
        file: resultPath,
        width: info.width,
        height: info.height,
        usage: body.usage,
      }),
    );
    if (info.width !== 2560 || info.height !== 2560)
      throw new Error("Model returned a different resolution; inspect before applying");
  }
}
if (process.argv.includes("--refine")) {
  const base = await fs.readFile(resultPath);
  const info = await sharp(base).metadata();
  if (info.width !== 2560 || info.height !== 2560)
    throw new Error("Patch refinement requires a 2560-square base");
  const wall = scene.splines!.find((s) => s.id === "ridge-curtain")!;
  const courtyard = wall.points.map((p) => `${p[0]},${p[1] / sin}`).join(" ");
  const keep = scene.groups.find((g) => g.name === "Tollkeeper's keep")!.transform;
  const yardSvg = svg.replace(
    "</svg>",
    `<polygon points="${courtyard}" fill="#9b896a"/>
    <path d="M2540 ${1370 / sin} L2630 ${1160 / sin} L${keep.dx} ${(keep.dy + 240) / sin}" stroke="#b9afa0" stroke-width="110" fill="none"/>
    <path d="M2630 ${1160 / sin} L3000 ${1160 / sin}" stroke="#b9afa0" stroke-width="70" fill="none"/>
    </svg>`,
  );
  const guide = await sharp(Buffer.from(yardSvg)).resize(2560, 2560).png().toBuffer();
  await fs.writeFile(path.join(out, "refinement-layout.svg"), yardSvg);
  await fs.writeFile(path.join(out, "refinement-layout.png"), guide);
  const patchPrompt = `Refine ONLY the terrain patch in image 1 into detailed native-resolution game ground. Image 1 is a crop of the existing base texture; preserve its exact framing, river position, bank shape, path locations and the fine-scale material palette. Increase actual detail, do not simply enlarge it. Image 2 is the matching exact layout drawing crop. It overrides image 1 inside the clearly bounded CASTLE COURTYARD polygon: replace the grass and rough rocks there with worn compacted ochre-brown earth, irregular aged limestone cobbles and flagstone paving along the pale gate-to-keep and stores approaches. The interior must clearly differ from the grassy exterior. Fill that polygon to its exact boundary, without painting walls or an outline; real 3D curtain walls will cover the boundary. No grass lawn inside the castle, only tiny weeds at paving joints. Elsewhere follow image 1, correcting path positions to image 2 if necessary. Image 3 shows the WHOLE base texture for color and spatial context only; do NOT output the whole image. Images 4 and 5 are original-game style references for grass, rocks, path dirt and water. Do not copy their objects or perspective. Strict flat overhead diffuse terrain, not isometric art. Do not add buildings, walls, bridges, fences, props, characters, cliffs, tall bushes, tree canopies, hard shadows, labels, frames or borders. Grass should be natural fine blades, stones small embedded pieces, banks muddy and water olive-brown with restrained ripples. Keep outer edge colors and features consistent with image 1 so the patch joins neighboring crops seamlessly. Output the entire first patch at exactly 2816x2816 pixels.`;
  const patchRoot = path.join(
    cache,
    "patches-" +
      crypto.createHash("sha256").update(base).update(guide).update(patchPrompt).digest("hex"),
  );
  await fs.mkdir(patchRoot, { recursive: true });
  const patches = [
    { x: 0, y: 0 },
    { x: 1152, y: 0 },
    { x: 0, y: 1152 },
    { x: 1152, y: 1152 },
  ];
  const headers = {
    Authorization: `Bearer ${requireEnv(identity.credential)}`,
    "Content-Type": "application/json",
  };
  for (const [i, patch] of patches.entries()) {
    const file = path.join(patchRoot, `patch-${i}.png`);
    try {
      await fs.access(file);
      continue;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
    const rect = { left: patch.x, top: patch.y, width: 1408, height: 1408 };
    const crop = await sharp(base).extract(rect).png().toBuffer();
    const cropGuide = await sharp(guide).extract(rect).png().toBuffer();
    await fs.writeFile(path.join(patchRoot, `input-${i}.png`), crop);
    await fs.writeFile(path.join(patchRoot, `guide-${i}.png`), cropGuide);
    const parameters = {
      model: identity.model,
      quality: "high",
      size: "2816x2816",
      n: "1",
      output_format: "png",
      prompt: patchPrompt,
    };
    await fs.writeFile(
      path.join(patchRoot, `request-${i}.json`),
      JSON.stringify(
        { parameters, rect, base_sha256: crypto.createHash("sha256").update(base).digest("hex") },
        null,
        2,
      ),
    );
    console.log("Generating terrain patch", i + 1, "of 4");
    const response = await fetch(identity.endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify(
        openRouterBody(parameters, crop, cropGuide, true, [
          base,
          ...references.map((r) => r.image),
        ]),
      ),
      signal: AbortSignal.timeout(600000),
    });
    const body = (await response.json()) as {
      data?: { b64_json?: string }[];
      usage?: unknown;
      error?: unknown;
    };
    await fs.writeFile(
      path.join(patchRoot, `response-${i}.json`),
      JSON.stringify({ status: response.status, usage: body.usage, error: body.error }, null, 2),
    );
    if (!response.ok || !body.data?.[0]?.b64_json)
      throw new Error(`Patch ${i} failed (${response.status}): ${JSON.stringify(body.error)}`);
    const png = Buffer.from(body.data[0].b64_json, "base64"),
      metadata = await sharp(png).metadata();
    if (metadata.width !== 2816 || metadata.height !== 2816)
      throw new Error("Unexpected patch dimensions");
    await fs.writeFile(file, png);
    console.log("Saved native patch", i + 1, JSON.stringify(body.usage));
  }
  const pixels = await Promise.all(
    patches.map((_, i) =>
      sharp(path.join(patchRoot, `patch-${i}.png`))
        .removeAlpha()
        .raw()
        .toBuffer(),
    ),
  );
  const size = 5120,
    tile = 2816,
    step = 2304,
    overlap = 512;
  const output = Buffer.alloc(size * size * 3);
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const tx = Math.max(0, Math.min(1, (x - step) / overlap));
      const ty = Math.max(0, Math.min(1, (y - step) / overlap));
      const weights = [(1 - tx) * (1 - ty), tx * (1 - ty), (1 - tx) * ty, tx * ty];
      for (let c = 0; c < 3; c++) {
        let value = 0;
        for (let i = 0; i < 4; i++)
          if (weights[i]! > 0) {
            const px = x - (i % 2) * step,
              py = y - Math.floor(i / 2) * step;
            value += pixels[i]![(py * tile + px) * 3 + c]! * weights[i]!;
          }
        output[(y * size + x) * 3 + c] = Math.round(value);
      }
    }
  finalPath = path.join(patchRoot, "terrain-5120.png");
  finalSize = 5120;
  await sharp(output, { raw: { width: size, height: size, channels: 3 } })
    .png()
    .toFile(finalPath);
  await fs.writeFile(
    path.join(cache, "refinement.json"),
    JSON.stringify(
      {
        model: identity.model,
        provider: identity.provider,
        prompt: patchPrompt,
        base_sha256: crypto.createHash("sha256").update(base).digest("hex"),
        patches,
        source_crop_size: 1408,
        native_patch_size: 2816,
        output_size: 5120,
        overlap_pixels: 512,
      },
      null,
      2,
    ),
  );
  console.log("Composed four native patches:", finalPath);
}
let metadataPath = path.join(
  cache,
  process.argv.includes("--refine") ? "refinement.json" : "request.json",
);
const textureIndex = process.argv.indexOf("--texture");
if (textureIndex >= 0) {
  const file = process.argv[textureIndex + 1];
  if (!file) throw new Error("--texture requires a generated PNG path");
  finalPath = path.resolve(file);
  const info = await sharp(finalPath).metadata();
  if (info.width !== info.height || ![2560, 5120].includes(info.width))
    throw new Error("Unexpected reviewed terrain dimensions");
  finalSize = info.width!;
  metadataPath =
    finalSize === 5120
      ? path.resolve(path.dirname(finalPath), "../refinement.json")
      : path.join(path.dirname(finalPath), "request.json");
}
if (process.argv.includes("--apply")) {
  const source = await fs.readFile(finalPath),
    info = await sharp(source).metadata();
  const texture = await sharp(source).jpeg({ quality: 95, chromaSubsampling: "4:4:4" }).toBuffer();
  if (info.width !== finalSize || info.height !== finalSize)
    throw new Error("Unexpected reviewed terrain dimensions");
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  const groundSource = scene.sceneAssets.find((asset) => asset.role === "ground");
  if (!groundSource) throw new Error("Map has no terrain asset");
  const gltf = await loadSceneModel(libraryDir, groundSource);
  const glbPath = path.join(cache, "updated-ground.glb");
  const root = gltf.getRoot().getDefaultScene() ?? gltf.getRoot().listScenes()[0]!;
  if (!root.listChildren().some((node) => node.getName() === "map")) {
    const wrapper = gltf.createNode("map");
    for (const child of root.listChildren()) wrapper.addChild(child);
    root.addChild(wrapper);
  }
  const ground = gltf
    .getRoot()
    .listNodes()
    .find((n) => n.getName() === "ground")!;
  ground
    .getMesh()!
    .listPrimitives()[0]!
    .getMaterial()!
    .getBaseColorTexture()!
    .setImage(texture)
    .setMimeType("image/jpeg");
  await io.write(glbPath, gltf);
  // Re-read the live document so unrelated scene edits made during generation survive.
  const current = await readStoredMap(scenePath, libraryDir);
  const imported = await importScene(
    glbPath,
    libraryDir,
    current as unknown as Record<string, unknown>,
  );
  current.sceneAssets = current.sceneAssets.map((asset) =>
    asset.id === groundSource.id
      ? imported.document.sceneAssets.find((asset) => asset.role === "ground")!
      : asset,
  );
  await fs.writeFile(
    scenePath,
    JSON.stringify(await compactStoredMap(current, libraryDir), null, 2) + "\n",
  );
  await fs.writeFile(path.join(libraryDir, "scenes/Wychford-ground.jpg"), texture);
  await fs.writeFile(new URL("../../maps/wychford/terrain.jpg", import.meta.url), texture);
  const evidence = JSON.parse(await fs.readFile(metadataPath, "utf8"));
  evidence.style_references = references.map((r) => ({
    file: r.file,
    description: r.description,
    sha256: crypto.createHash("sha256").update(r.image).digest("hex"),
  }));
  evidence.runtime_encoding = {
    format: "jpeg",
    quality: 95,
    chroma_subsampling: "4:4:4",
    width: finalSize,
    height: finalSize,
  };
  await fs.writeFile(
    new URL("../../maps/wychford/terrain-generation.json", import.meta.url),
    JSON.stringify(evidence, null, 2) + "\n",
  );
  await fs.copyFile(
    path.join(out, "refinement-layout.svg"),
    new URL("../../maps/wychford/terrain-layout.svg", import.meta.url),
  );
  console.log("Updated terrain texture; scene geometry and population preserved");
}
console.log("Generation cache:", cache);
