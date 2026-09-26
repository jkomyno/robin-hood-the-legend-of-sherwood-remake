import { defineConfig } from "vite";
import solid from "vite-plugin-solid";
import { fileURLToPath } from "node:url";
import { createReadStream } from "node:fs";
import { readdir, realpath, stat } from "node:fs/promises";
import path from "node:path";

const library = path.resolve(fileURLToPath(new URL("../library/", import.meta.url)));
const mime: Record<string, string> = {
  ".json": "application/json",
  ".glb": "model/gltf-binary",
  ".bin": "application/octet-stream",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".avif": "image/avif",
};

function mountLibrary(server: import("vite").ViteDevServer | import("vite").PreviewServer) {
  server.middlewares.use((request, response, next) => {
    const url = request.url?.split("?", 1)[0] ?? "";
    if (!url.startsWith("/library/")) return next();
    void (async () => {
      if (request.method !== "GET" && request.method !== "HEAD") {
        response.writeHead(405).end();
        return;
      }
      let parts: string[];
      try {
        parts = url.slice("/library/".length).split("/").map(decodeURIComponent);
      } catch {
        response.writeHead(400).end();
        return;
      }
      if (
        parts.some(
          (part) => !part || part.startsWith(".") || part === "backups" || /[\\/\0]/.test(part),
        )
      ) {
        response.writeHead(404).end();
        return;
      }
      if (parts.join("/") === "scenes/index.json") {
        const names = (await readdir(path.join(library, "scenes")))
          .filter((name) => name.endsWith(".rhlos-map.json"))
          .sort((a, b) => a.localeCompare(b));
        response.writeHead(200, {
          "Content-Type": "application/json",
          "Cache-Control": "no-cache",
        });
        response.end(request.method === "HEAD" ? undefined : JSON.stringify(names) + "\n");
        return;
      }
      try {
        const file = await realpath(path.join(library, ...parts));
        if (!file.startsWith(library + path.sep)) throw new Error("Outside library");
        const info = await stat(file);
        if (!info.isFile()) throw new Error("Not a file");
        response.writeHead(200, {
          "Content-Type": mime[path.extname(file).toLowerCase()] ?? "application/octet-stream",
          "Content-Length": info.size,
          "Cache-Control": "no-cache",
        });
        if (request.method === "HEAD") response.end();
        else createReadStream(file).pipe(response);
      } catch {
        response.writeHead(404).end();
      }
    })().catch(next);
  });
}

function serveLibrary() {
  return {
    name: "serve-library",
    configureServer: mountLibrary,
    configurePreviewServer: mountLibrary,
  };
}

export default defineConfig({
  plugins: [solid(), serveLibrary()],
  publicDir: false,
  server: { port: 5180, fs: { allow: [fileURLToPath(new URL("../../", import.meta.url))] } },
  build: { target: "esnext", copyPublicDir: false },
});
