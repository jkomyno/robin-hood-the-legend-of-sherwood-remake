import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Create a static, generated view of the library; never copy its large binaries.
const app = path.dirname(fileURLToPath(import.meta.url));
const source = path.resolve(app, "../library");
const destination = path.join(
  app,
  process.argv.includes("--preview") ? "dist" : ".library-public",
  "library",
);
await fs.mkdir(destination, { recursive: true });
const catalog = [];
async function walk(relative = "") {
  for (const entry of await fs.readdir(path.join(source, relative), { withFileTypes: true })) {
    if (entry.name.startsWith(".") || entry.name === "backups" || entry.isSymbolicLink()) continue;
    const name = path.posix.join(relative, entry.name);
    if (name === "3d-assets") continue;
    if (name === "scenes/index.json") continue;
    if (entry.isDirectory()) await walk(name);
    else if (entry.isFile()) {
      catalog.push(name);
      const target = path.join(destination, name);
      await fs.mkdir(path.dirname(target), { recursive: true });
      try {
        await fs.symlink(path.join(source, name), target);
      } catch (error) {
        if (error.code !== "EEXIST") throw error;
      }
    }
  }
}
await walk();
// Link the asset directory itself so assets published while Vite is running appear at once.
const assets = path.join(destination, "3d-assets");
const assetSource = path.join(source, "3d-assets");
try {
  const entry = await fs.lstat(assets);
  if (!entry.isSymbolicLink() || (await fs.readlink(assets)) !== assetSource) {
    await fs.rm(assets, { recursive: true });
    await fs.symlink(assetSource, assets, "dir");
  }
} catch (error) {
  if (error.code !== "ENOENT") throw error;
  await fs.symlink(assetSource, assets, "dir");
}
// Remove links retired by a publication, without following them into the library.
const active = new Set([...catalog, "3d-assets"]);
async function prune(relative = "") {
  for (const entry of await fs.readdir(path.join(destination, relative), { withFileTypes: true })) {
    const name = path.posix.join(relative, entry.name);
    if (entry.isDirectory()) await prune(name);
    else if (entry.isSymbolicLink() && !active.has(name))
      await fs.unlink(path.join(destination, name));
  }
}
await prune();
await fs.mkdir(path.join(destination, "scenes"), { recursive: true });
await fs.writeFile(
  path.join(destination, "scenes/index.json"),
  JSON.stringify(
    catalog
      .filter((name) => /^scenes\/[^/]+\.rhlos-map\.json$/.test(name))
      .map((name) => name.slice("scenes/".length))
      .sort((a, b) => a.localeCompare(b)),
  ) + "\n",
);
console.log(`Prepared ${catalog.length} scene files and linked the live asset library.`);
