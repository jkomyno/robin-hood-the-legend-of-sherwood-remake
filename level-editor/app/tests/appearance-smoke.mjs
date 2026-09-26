import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromeEndpoint, evaluate, socketOpen } from "./cdp.mjs";

const profile = await mkdtemp(join(tmpdir(), "appearance-"));
const chrome = spawn(
  process.env.CHROME ?? "chromium",
  [
    "--headless",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: ["ignore", "ignore", "pipe"] },
);
let socket;
try {
  const endpoint = await chromeEndpoint(chrome, { timeoutMs: 15000 });
  const pages = await (await fetch(`http://${new URL(endpoint).host}/json/list`)).json();
  socket = new WebSocket(pages.find((page) => page.type === "page").webSocketDebuggerUrl);
  await socketOpen(socket, { timeoutMs: 5000 });
  let id = 1;
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const requestId = id++;
      const onMessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.id !== requestId) return;
        socket.removeEventListener("message", onMessage);
        if (message.error) reject(new Error(JSON.stringify(message.error)));
        else resolve(message.result);
      };
      socket.addEventListener("message", onMessage);
      socket.send(JSON.stringify({ id: requestId, method, params }));
    });
  await send("Page.enable");
  await send("Page.addScriptToEvaluateOnNewDocument", {
    source: `window.__warnings = []; const oldWarn = console.warn;
      console.warn = (...args) => {
        window.__warnings.push({ message: String(args[0]), stack: new Error().stack });
        oldWarn(...args);
      };`,
  });
  await send("Page.navigate", { url: process.env.EDITOR_URL ?? "http://127.0.0.1:5180" });
  const run = (expression) => evaluate(socket, id++, expression);
  const until = async (expression) => {
    for (let attempt = 0; attempt < 50; attempt++) {
      const value = await run(expression);
      if (value) return value;
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
    throw new Error(`Timed out: ${expression}`);
  };
  await until(`document.querySelector("input[aria-label='Find assets']") &&
    document.querySelectorAll(".asset-card").length > 0`);
  await run(`(() => {
    const input = document.querySelector("input[aria-label='Find assets']");
    input.value = "leicester-east-moat-drawbridge";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  })()`);
  await until(`document.querySelectorAll(".asset-card").length === 1`);
  await run(`document.querySelector(".asset-card").dispatchEvent(
    new PointerEvent("pointerenter", { bubbles: false }))`);
  await until(
    `document.querySelector(".asset-card select[aria-label$='appearance']")?.options.length === 2`,
  );
  const result = await run(`(() => {
    const card = document.querySelector(".asset-card");
    const select = card.querySelector("select[aria-label$='appearance']");
    return {
      cards: document.querySelectorAll(".asset-card").length,
      options: Array.from(select.options).map(option => option.textContent),
      title: card.querySelector("strong").textContent,
    };
  })()`);
  assert.equal(result.cards, 1);
  assert.deepEqual(result.options, ["Initial", "Applied endpoint"]);
  await run(`(() => {
    const select = document.querySelector("select[aria-label='Map']");
    const option = Array.from(select.options).find(option => option.value.toLowerCase() === "derby");
    if (!option) throw new Error("Derby map is unavailable");
    select.value = option.value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  })()`);
  await until(`Number(document.querySelector(".object-count")?.textContent) > 0`);
  assert.deepEqual(await run(`window.__warnings`), []);
  console.log("One drawbridge card with two appearances; Derby loads without Solid warnings");
} finally {
  socket?.close();
  if (chrome.exitCode === null && chrome.signalCode === null) {
    const exit = new Promise((resolve) => chrome.once("exit", resolve));
    chrome.kill("SIGTERM");
    await exit;
  }
  await rm(profile, { recursive: true, force: true, maxRetries: 3 });
}
