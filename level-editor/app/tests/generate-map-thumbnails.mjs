// Run against the dev server. Native canvas encoding is shared with Save.
import { spawn } from "node:child_process";
import { mkdtemp, readdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromeEndpoint, socketOpen, evaluate } from "./cdp.mjs";
const base = process.argv[2] ?? "http://127.0.0.1:5180";
const existing = await readdir("library/scenes");
const maps = existing
  .filter((name) => name.endsWith(".rhlos-map.json"))
  .map((name) => name.replace(".rhlos-map.json", ""))
  .filter(
    (name) =>
      !process.argv.includes("--missing") ||
      !["avif", "webp", "png"].some((ext) => existing.includes(`${name}.${ext}`)),
  );
const profile = await mkdtemp(join(tmpdir(), "map-thumbnails-"));
const chrome = spawn(
  process.env.CHROME ?? "chromium",
  [
    "--headless",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--enable-unsafe-swiftshader",
    "--use-angle=swiftshader",
    "--window-size=1440,1000",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: ["ignore", "ignore", "pipe"] },
);
const closed = new Promise((resolve) => chrome.once("close", resolve));
const evaluateLong = (socket, id, expression, options = {}) =>
  evaluate(socket, id, expression, { timeoutMs: 60000, ...options });
let socket;
try {
  const endpoint = new URL(await chromeEndpoint(chrome));
  const pages = await (await fetch(`http://${endpoint.host}/json/list`)).json();
  socket = new WebSocket(pages.find((page) => page.type === "page").webSocketDebuggerUrl);
  await socketOpen(socket);
  let id = 0;
  for (const map of maps) {
    console.log(`Rendering ${map}`);
    await evaluateLong(
      socket,
      ++id,
      `location.href = ${JSON.stringify(`${base}/tests/authored-scene.html?map=${encodeURIComponent(map)}&view`)}`,
    );
    let ready = false;
    let loadError;
    for (let attempt = 0; attempt < 600; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 200));
      const status = await evaluateLong(
        socket,
        ++id,
        'document.querySelector("#result")?.textContent',
        { timeoutMs: 60000 },
      );
      if (status?.startsWith("FAIL")) {
        loadError = status;
        break;
      }
      if (status === "READY") {
        ready = true;
        break;
      }
    }
    if (loadError) {
      console.warn(`${map}: ${loadError}; using the shipped map artwork for its preview.`);
      const original =
        {
          nottingham: "Nottingham",
          derby: "Derby",
          croisement01: "Croisement01",
          croisement02: "Croisement02",
          croisement03: "Croisement03",
        }[map] ?? map;
      await evaluateLong(
        socket,
        ++id,
        `(async () => {
        const image = new Image(); image.src = ${JSON.stringify(`${base}/library/game-data/Data/Levels/Day/`)} + ${JSON.stringify(original)} + ".map.png";
        await image.decode();
        const canvas = document.createElement("canvas"); canvas.width = 480; canvas.height = 300;
        const ctx = canvas.getContext("2d"); ctx.fillStyle = "#1c1c1c"; ctx.fillRect(0,0,480,300);
        const scale = Math.min(480/image.width,300/image.height);
        ctx.drawImage(image,(480-image.width*scale)/2,(300-image.height*scale)/2,image.width*scale,image.height*scale);
        const { encodeMapThumbnail } = await import("/src/map-thumbnail.ts");
        const blob = await encodeMapThumbnail(canvas);
        window.__thumbnail = { type: blob.type, bytes: Array.from(new Uint8Array(await blob.arrayBuffer())) };
      })().catch(error => { window.__thumbnailError = String(error); })`,
      );
    } else {
      console.log(`Loaded ${map}`);
      if (!ready) throw new Error(`Timed out loading ${map}`);
      await evaluateLong(
        socket,
        ++id,
        "window.captureMapThumbnail().then(result => { window.__thumbnail = result; })",
      );
    }
    let result;
    for (let n = 0; n < 600; n++) {
      await new Promise((resolve) => setTimeout(resolve, 50));
      result = await evaluateLong(socket, ++id, "window.__thumbnail");
      if (result) break;
    }
    if (!result) throw new Error("Native thumbnail encoding timed out");
    const extension = { "image/avif": "avif", "image/webp": "webp", "image/png": "png" }[
      result.type
    ];
    if (!extension) throw new Error(`Unexpected native encoder output ${result.type}`);
    await writeFile(`library/scenes/${map}.${extension}`, new Uint8Array(result.bytes));
    console.log(`${map}.${extension}: ${result.bytes.length} bytes`);
  }
} finally {
  socket?.close();
  chrome.kill("SIGTERM");
  await closed;
  await rm(profile, { recursive: true, force: true });
}
