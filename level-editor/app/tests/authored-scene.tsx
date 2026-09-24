// Read-only local review of generated library scenes; served by the Vite dev server.
import { render } from "@solidjs/web";
import Editor3D from "../src/Editor3D";
import "../src/styles.css";

const query = new URLSearchParams(location.search);
const map = query.get("map") ?? "Wychford";
if (!/^[a-zA-Z0-9_-]+$/.test(map)) throw new Error("Invalid scene name");
const root = new URL("../../library/scenes/Wychford-volumes.scene.json", import.meta.url).pathname;
const result = document.querySelector("#result")!;
const files = [map + "-volumes.scene.glb", map + "-volumes.scene.json", map + ".level3d.json"];
const directory = (prefix: string): FileSystemDirectoryHandle => ({
  name: "library", kind: "directory",
  async getDirectoryHandle(name: string) { return directory(prefix + name + "/"); },
  async getFileHandle(name: string) {
    const response = await fetch(root.slice(0, root.lastIndexOf("/scenes/") + 1) + prefix + name);
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
  style.textContent = ".shared-library,.editor-panel,.editor-bar,#result{display:none!important}";
  document.head.appendChild(style);
}
const library = { handle: directory("") };
render(() => <Editor3D index={() => null} library={() => library}
  onError={error => { result.textContent = "FAIL " + error; }}
  onStatus={status => {
    if (status === null) setTimeout(() => { if (!result.textContent?.startsWith("FAIL")) result.textContent = "READY"; }, 1800);
    else result.textContent = status;
  }} />, document.querySelector("#root")!);
