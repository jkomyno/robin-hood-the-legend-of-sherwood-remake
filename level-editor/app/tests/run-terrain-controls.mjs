import { spawn } from "node:child_process";
import { mkdtemp, rm, writeFile, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import assert from "node:assert/strict";
import { chromeEndpoint, socketOpen, evaluate } from "./cdp.mjs";
const profile = await mkdtemp(join(tmpdir(), "terrain-controls-"));
const chrome = spawn(
  process.env.CHROME ?? "chromium",
  [
    "--headless",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--window-size=1440,1000",
    "--enable-unsafe-swiftshader",
    "--use-angle=swiftshader",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    `${process.argv[2] ?? "http://127.0.0.1:5197"}/tests/terrain-workflow.html?controls`,
  ],
  { stdio: ["ignore", "ignore", "pipe"] },
);
let socket,
  id = 0;
const sleep = () => new Promise((r) => setTimeout(r, 100));
function command(method, params = {}) {
  return new Promise((resolve, reject) => {
    const request = ++id;
    const timer = setTimeout(() => {
      socket.removeEventListener("message", listen);
      reject(new Error(`Timeout ${method}`));
    }, 10000);
    const listen = (event) => {
      const result = JSON.parse(String(event.data));
      if (result.id !== request) return;
      clearTimeout(timer);
      socket.removeEventListener("message", listen);
      if (result.error) reject(new Error(JSON.stringify(result.error)));
      else resolve(result.result);
    };
    socket.addEventListener("message", listen);
    socket.send(JSON.stringify({ id: request, method, params }));
  });
}
const evalJS = (source) => evaluate(socket, ++id, source, { timeoutMs: 10000 });
async function mouse(type, p, modifiers = 0) {
  await command("Input.dispatchMouseEvent", {
    type,
    x: p.x,
    y: p.y,
    button: "left",
    buttons: type === "mouseReleased" ? 0 : 1,
    clickCount: 1,
    modifiers,
  });
  await sleep();
}
async function drag(from, to, cancel = false, modifiers = 0) {
  await mouse("mouseMoved", from, modifiers);
  await mouse("mousePressed", from, modifiers);
  await mouse("mouseMoved", to, modifiers);
  if (cancel)
    await command("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "Escape",
      code: "Escape",
      windowsVirtualKeyCode: 27,
    });
  await mouse("mouseReleased", to);
  await sleep();
}
try {
  const endpoint = new URL(await chromeEndpoint(chrome, { timeoutMs: 15000 }));
  let page;
  for (let i = 0; i < 50 && !page; i++) {
    page = (await (await fetch(`http://${endpoint.host}/json/list`)).json()).find(
      (p) => p.type === "page",
    );
    if (!page) await sleep();
  }
  assert.ok(page);
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await socketOpen(socket);
  let ready;
  for (let i = 0; i < 150; i++) {
    try {
      ready = await evalJS("document.querySelector('#result')?.textContent");
    } catch {}
    if (ready === "READY" || ready?.startsWith("FAIL")) break;
    await sleep();
  }
  assert.equal(ready, "READY");
  let before = await evalJS("terrainTest.state()"),
    vertex = await evalJS("terrainTest.point(9)");
  await drag(vertex, { x: vertex.x, y: vertex.y - 25 });
  let after = await evalJS("terrainTest.state()");
  assert.equal(after.commits, before.commits + 1);
  assert.notEqual(
    after.document.terrain.vertices[9].position[2],
    before.document.terrain.vertices[9].position[2],
  );
  before = after;
  vertex = await evalJS("terrainTest.point(9)");
  await drag(vertex, { x: vertex.x, y: vertex.y - 20 }, true);
  after = await evalJS("terrainTest.state()");
  assert.equal(after.commits, before.commits);
  assert.deepEqual(after.document, before.document);
  vertex = await evalJS("terrainTest.point(9)");
  await drag(vertex, { x: vertex.x + 15, y: vertex.y + 10 }, false, 8);
  after = await evalJS("terrainTest.state()");
  assert.equal(after.commits, before.commits + 1);
  assert.notDeepEqual(
    after.document.terrain.vertices[9].position.slice(0, 2),
    before.document.terrain.vertices[9].position.slice(0, 2),
  );
  assert.equal(
    after.document.terrain.vertices[9].position[2],
    before.document.terrain.vertices[9].position[2],
  );
  before = after;
  const number = await evalJS(
    `(()=>{const r=document.querySelector('[aria-label="Vertex Z"]').closest('.meta-row').querySelector('.meta-key').getBoundingClientRect();return {x:r.left+10,y:r.top+r.height/2};})()`,
  );
  await drag(number, { x: number.x + 25, y: number.y });
  after = await evalJS("terrainTest.state()");
  assert.equal(after.commits, before.commits + 1);
  assert.equal(
    after.document.terrain.vertices[9].position[2],
    Math.round((before.document.terrain.vertices[9].position[2] + 25) * 100) / 100,
  );
  before = after;
  await drag(number, { x: number.x + 25, y: number.y }, true);
  after = await evalJS("terrainTest.state()");
  assert.equal(after.commits, before.commits);
  assert.deepEqual(after.document, before.document);
  await evalJS("terrainTest.selectCell(0)");
  await sleep();
  await evalJS(
    `Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Subdivide selected cell').click()`,
  );
  await sleep();
  after = await evalJS("terrainTest.state()");
  assert.ok(after.document.terrain.cells.length > before.document.terrain.cells.length);
  assert.equal(after.commits, before.commits + 1);
  assert.deepEqual(after.errors, []);
  if (process.env.TEST_ARTIFACT_DIR) {
    await mkdir(process.env.TEST_ARTIFACT_DIR, { recursive: true });
    const image = await command("Page.captureScreenshot");
    await writeFile(
      join(process.env.TEST_ARTIFACT_DIR, "terrain-controls.png"),
      Buffer.from(image.data, "base64"),
    );
  }
  console.log(
    "PASS real pointer vertex elevation, Shift horizontal movement, one commit per drag, Escape cancellation, number scrubbing and cell subdivision",
  );
} catch (error) {
  console.error(error);
  if (socket && process.env.TEST_ARTIFACT_DIR) {
    await mkdir(process.env.TEST_ARTIFACT_DIR, { recursive: true });
    const image = await command("Page.captureScreenshot");
    await writeFile(
      join(process.env.TEST_ARTIFACT_DIR, "terrain-controls-failure.png"),
      Buffer.from(image.data, "base64"),
    );
  }
  throw error;
} finally {
  socket?.close();
  const exited = new Promise((r) => chrome.once("close", r));
  chrome.kill("SIGTERM");
  await Promise.race([exited, new Promise((r) => setTimeout(r, 3000))]);
  if (chrome.exitCode === null) chrome.kill("SIGKILL");
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
}
