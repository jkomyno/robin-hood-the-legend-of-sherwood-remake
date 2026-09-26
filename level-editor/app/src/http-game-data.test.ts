import test from "node:test";
import assert from "node:assert/strict";
import { openHttpGameData } from "./http-game-data.ts";
import { readJson, isNotFound } from "./fs.ts";

test("HTTP game data indexes missions and preserves enumerated sprite handles and missing paths", async (t) => {
  const files = {
    "Data/Levels/York.rhp.json": "{}",
    "Data/Levels/H01.rhm.json": JSON.stringify({ header: { map_filename: "York" } }),
    "Data/Characters/Guard B00.rhs.d/manifest.json": JSON.stringify({ profiles: [] }),
    "Data/Characters/Guard B00.rhs.d/Idle/00.png": "pixels",
  };
  const requests: string[] = [];
  t.mock.method(globalThis, "fetch", async (url: string) => {
    requests.push(url);
    const path = decodeURIComponent(url.slice("/fixture/".length));
    const body =
      path === "index.json"
        ? JSON.stringify({ version: 1, files: Object.keys(files) })
        : files[path as keyof typeof files];
    return new Response(body ?? "", { status: body === undefined ? 404 : 200 });
  });
  const index = await openHttpGameData("/fixture/");
  assert.deepEqual([...index.maps], ["York"]);
  assert.equal(index.missionEntries?.[0]?.map, "York");
  assert.equal(requests.length, 2, "unused maps and sprites must load lazily");
  const data = await index.root!.getDirectoryHandle("Data");
  const characters = await data.getDirectoryHandle("Characters");
  await assert.rejects(characters.getDirectoryHandle("guard b00.rhs.d"), isNotFound);
  const entries = [];
  for await (const entry of characters.entries()) entries.push(entry);
  const bank = entries[0]![1] as FileSystemDirectoryHandle;
  assert.deepEqual(await readJson(bank, "manifest.json"), { profiles: [] });
  const idle = await bank.getDirectoryHandle("Idle");
  assert.equal(await (await (await idle.getFileHandle("00.png")).getFile()).text(), "pixels");
  assert.ok(requests.some((url) => url.includes("Guard%20B00.rhs.d")));
  await assert.rejects(bank.getFileHandle("missing.json"), isNotFound);
  await assert.rejects(bank.getFileHandle("manifest.json", { create: true }), {
    name: "NotAllowedError",
  });
  await assert.rejects(bank.getDirectoryHandle(".."), /Invalid game data path/);
});

test("missing HTTP game data reports the preparation command", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response("", { status: 404 }));
  await assert.rejects(openHttpGameData("/missing/"), /pnpm library:game-data/);
});

test("HTTP game data rejects unsafe catalog paths", async (t) => {
  t.mock.method(globalThis, "fetch", async () =>
    Response.json({ version: 1, files: ["../secret"] }),
  );
  await assert.rejects(openHttpGameData("/fixture/"), /Invalid game data path/);
});
