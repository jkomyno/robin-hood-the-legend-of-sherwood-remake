// Read-only local review of generated library scenes; served by the Vite dev server.
import { render } from "@solidjs/web";
import { EditorViewport } from "../src/editor-viewport";
import { encodeMapThumbnail } from "../src/map-thumbnail";
import Editor3D from "../src/Editor3D";
import "../src/styles.css";

const query = new URLSearchParams(location.search);
const map = query.get("map") ?? "Wychford";
if (!/^[a-zA-Z0-9_-]+$/.test(map)) throw new Error("Invalid scene name");
const root = "/library/";
const result = document.querySelector("#result")!;
const files = [map + ".rhlos-map.json"];
const directory = (prefix: string): FileSystemDirectoryHandle =>
  ({
    name: "library",
    kind: "directory",
    async getDirectoryHandle(name: string) {
      return directory(prefix + name + "/");
    },
    async getFileHandle(name: string) {
      const response = await fetch(root + prefix + name);
      if (response.status === 404) throw new DOMException("Missing thumbnail", "NotFoundError");
      if (!response.ok) throw new Error("Failed to read " + prefix + name + ": " + response.status);
      const file = new File([await response.arrayBuffer()], name);
      return { getFile: async () => file };
    },
    async *entries() {
      if (prefix === "scenes/") for (const file of files) yield [file, { kind: "file" }];
    },
  }) as unknown as FileSystemDirectoryHandle;
if (query.has("view")) {
  const style = document.createElement("style");
  style.textContent =
    ".asset-browser,.shared-library,.editor-panel,.editor-bar,#result{display:none!important}";
  document.head.appendChild(style);
}
const setup = EditorViewport.prototype.setup;
EditorViewport.prototype.setup = function (element) {
  setup.call(this, element);
  const viewport = this;
  Object.assign(window, {
    async captureMapThumbnail() {
      const blob = await encodeMapThumbnail(viewport.captureThumbnail());
      return { type: blob.type, bytes: Array.from(new Uint8Array(await blob.arrayBuffer())) };
    },
  });
};
const library = { handle: directory("") };
render(
  () => (
    <Editor3D
      index={() => null}
      library={() => library}
      onError={(error) => {
        result.textContent = "FAIL " + error;
      }}
      onStatus={(status) => {
        if (status === null)
          setTimeout(() => {
            if (
              !result.textContent?.startsWith("FAIL") &&
              document.querySelector("[data-map-name]") &&
              !document.querySelector(".map-load-dialog")
            )
              result.textContent = "READY";
          }, 1800);
        else result.textContent = status;
      }}
    />
  ),
  document.querySelector("#root")!,
);

// This review fixture explicitly opens its requested map; the editor starts at Select Map.
const openRequested = setInterval(() => {
  const card = document.querySelector<HTMLButtonElement>(".map-card-open");
  if (card) {
    clearInterval(openRequested);
    card.click();
  }
}, 50);
