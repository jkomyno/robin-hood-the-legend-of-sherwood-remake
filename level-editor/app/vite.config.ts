import { defineConfig } from "vite";
import solid from "vite-plugin-solid";
import { fileURLToPath } from "node:url";
import { createReadStream } from "node:fs";
import { realpath, stat } from "node:fs/promises";
import path from "node:path";

const library = path.resolve(fileURLToPath(new URL("../library/", import.meta.url)));
const contentTypes: Record<string, string> = {
  ".json": "application/json",
  ".glb": "model/gltf-binary",
  ".bin": "application/octet-stream",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".avif": "image/avif",
};

/** Read the live library in dev, including assets published after Vite started. */
function liveLibrary() {
  return {
    name: "live-library",
    configureServer(server: import("vite").ViteDevServer) {
      server.middlewares.use((request, response, next) => {
        const pathname = request.url?.split("?", 1)[0] ?? "";
        if (!pathname.startsWith("/library/") || pathname === "/library/scenes/index.json")
          return next();
        if (request.method !== "GET" && request.method !== "HEAD") {
          response.writeHead(405).end();
          return;
        }
        void (async () => {
          let segments: string[];
          try {
            segments = pathname.slice("/library/".length).split("/").map(decodeURIComponent);
          } catch {
            response.writeHead(400).end();
            return;
          }
          if (
            segments.some(
              (part) => !part || part.startsWith(".") || part === "backups" || /[\\/\0]/.test(part),
            )
          ) {
            response.writeHead(404).end();
            return;
          }
          const file = path.join(library, ...segments);
          try {
            const actual = await realpath(file);
            if (!actual.startsWith(library + path.sep))
              throw new Error("Library path escapes root");
            const info = await stat(actual);
            if (!info.isFile()) throw new Error("Library path is not a file");
            response.writeHead(200, {
              "Content-Type":
                contentTypes[path.extname(file).toLowerCase()] ?? "application/octet-stream",
              "Content-Length": info.size,
              "Cache-Control": "no-cache",
            });
            if (request.method === "HEAD") response.end();
            else createReadStream(actual).pipe(response);
          } catch {
            response.writeHead(404).end();
          }
        })();
      });
    },
  };
}

export default defineConfig({
  plugins: [solid(), liveLibrary()],
  publicDir: ".library-public",
  server: { port: 5180, fs: { allow: [fileURLToPath(new URL("../../", import.meta.url))] } },
  build: { target: "esnext", copyPublicDir: false },
});
