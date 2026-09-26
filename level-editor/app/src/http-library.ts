import { publishedMapLabel } from "./map-label.ts";
import { isNotFound } from "./fs.ts";

async function migrateBrowserMaps(maps: FileSystemDirectoryHandle) {
  const legacyExtension = ".level3d.json";
  const pending: string[] = [];
  for await (const [name, entry] of maps.entries())
    if (entry.kind === "file" && name.endsWith(legacyExtension)) pending.push(name);
  for (const name of pending) {
    const destination = name.slice(0, -legacyExtension.length) + ".rhlos-map.json";
    try {
      await maps.getFileHandle(destination);
      continue; // An existing new-format save takes precedence; retain the older file for recovery.
    } catch (error) {
      if (!isNotFound(error)) throw error;
    }
    const source = await (await maps.getFileHandle(name)).getFile();
    const output = await maps.getFileHandle(destination, { create: true });
    const writer = await output.createWritable();
    try {
      await writer.write(source);
      await writer.close();
    } catch (error) {
      await writer.abort().catch(() => {});
      await maps.removeEntry(destination);
      throw error;
    }
    await maps.removeEntry(name);
  }
}

const missing = (path: string) =>
  new DOMException(`Missing library file: ${path}`, "NotFoundError");
function segment(name: string) {
  if (!name || name === "." || name === ".." || /[\\/\0]/.test(name))
    throw new Error("Invalid library path");
  return name;
}

/** Read-only HTTP originals and separately selectable browser-local map copies. */
export async function openHttpLibrary(base = "/library/", storage?: FileSystemDirectoryHandle) {
  const response = await fetch(base + "3d-assets/index.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Cannot load library catalog (${response.status})`);
  const catalog = await response.json();
  if (!catalog || !Array.isArray(catalog.assets)) throw new Error("Invalid asset library index");
  const browser = storage ?? (await navigator.storage.getDirectory());
  const workspace = await browser.getDirectoryHandle("sherwood-level-editor", { create: true });
  const maps = await workspace.getDirectoryHandle("maps", { create: true });
  await migrateBrowserMaps(maps);
  const remoteFile = async (path: string) => {
    const result = await fetch(base + path.split("/").map(encodeURIComponent).join("/"), {
      cache: "no-cache",
    });
    if (result.status === 404) throw missing(path);
    if (!result.ok) throw new Error(`Cannot read ${path} (${result.status})`);
    if (result.headers.get("content-type")?.includes("text/html")) throw missing(path);
    return new File([await result.arrayBuffer()], path.split("/").at(-1)!, {
      type: result.headers.get("content-type") ?? "",
    });
  };
  const published: unknown = JSON.parse(await (await remoteFile("scenes/index.json")).text());
  if (
    !Array.isArray(published) ||
    published.some((name) => typeof name !== "string" || !name.endsWith(".rhlos-map.json"))
  )
    throw new Error("Invalid map index");
  const publishedNames = published.map((name) => segment(name as string));
  const publishedFiles = new Set(publishedNames);
  const extension = ".rhlos-map.json";
  const modifiedSuffix = " (Modified)";
  // Copy labels are virtual names; stored map names and document IDs stay unchanged.
  const documentMap = (name: string) =>
    name.endsWith(modifiedSuffix) &&
    publishedFiles.has(name.slice(0, -modifiedSuffix.length) + extension)
      ? name.slice(0, -modifiedSuffix.length)
      : name;
  const savedMapName = (name: string) =>
    publishedFiles.has(name + extension) ? name + modifiedSuffix : name;
  async function mapLabels() {
    const local = new Set<string>();
    for await (const [name, entry] of maps.entries()) if (entry.kind === "file") local.add(name);
    const labels = new Map<string, string>();
    for (const file of publishedNames) {
      const name = file.slice(0, -extension.length);
      labels.set(name, publishedMapLabel(name, false));
      if (local.has(file)) labels.set(savedMapName(name), publishedMapLabel(name, true));
    }
    return labels;
  }
  function directory(prefix: string): FileSystemDirectoryHandle {
    const isMaps = prefix === "scenes/";
    return {
      kind: "directory",
      name: prefix ? prefix.split("/").at(-2)! : "HTTP library",
      async getDirectoryHandle(name: string) {
        const next = prefix + segment(name) + "/";
        return directory(next);
      },
      async getFileHandle(name: string, options?: FileSystemGetFileOptions) {
        const path = prefix + segment(name);
        if (isMaps && name.endsWith(".rhlos-map.json")) {
          const id = name.slice(0, -extension.length);
          const source = documentMap(id);
          if (source !== id) return maps.getFileHandle(source + extension, options);
          if (!publishedFiles.has(name)) return maps.getFileHandle(name, options);
          return {
            kind: "file",
            name,
            getFile: async () => remoteFile(path),
            async createWritable() {
              return (await maps.getFileHandle(name, { create: true })).createWritable();
            },
          } as FileSystemFileHandle;
        }
        if (options?.create)
          throw new DOMException("Library assets are read-only", "NotAllowedError");
        const file = await remoteFile(path);
        return { kind: "file", name, getFile: async () => file } as FileSystemFileHandle;
      },
      async *entries() {
        const names = new Map<string, "file" | "directory">();
        if (!isMaps)
          throw new Error("Only map enumeration is supported; use the asset index for assets");
        for (const name of publishedNames) names.set(name, "file");
        for await (const [name, entry] of maps.entries())
          if (entry.kind === "file" && name.endsWith(extension))
            names.set(savedMapName(name.slice(0, -extension.length)) + extension, "file");
        for (const [name, kind] of names)
          yield [name, kind === "directory" ? directory(prefix + name + "/") : { kind, name }] as [
            string,
            FileSystemHandle,
          ];
      },
      async removeEntry(name: string) {
        if (!isMaps || !segment(name).endsWith(".rhlos-map.json"))
          throw new DOMException("Library assets are read-only", "NotAllowedError");
        await maps.removeEntry(documentMap(name.slice(0, -extension.length)) + extension);
      },
    } as unknown as FileSystemDirectoryHandle;
  }
  return { handle: directory(""), mapLabels, documentMap, savedMapName };
}

export function downloadMap(name: string, document: unknown) {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  const timestamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}`;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(document, null, 2) + "\n"], { type: "application/json" }),
  );
  const link = window.document.createElement("a");
  link.href = url;
  link.download = `${name}_${timestamp}.rhlos-map.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
