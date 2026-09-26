import { scanDatadir } from "./datadir.ts";
import { loadMissionCatalog } from "./mission-catalog.ts";

function segment(name: string) {
  if (!name || name === "." || name === ".." || /[\\/\0]/.test(name))
    throw new Error("Invalid game data path");
  return name;
}

/** Indexed HTTP directory handles retain the loaders' enumeration and missing-file semantics. */
export async function openHttpGameData(
  base = (import.meta.env?.BASE_URL ?? "/") + "library/game-data/",
) {
  async function read(path: string) {
    const response = await fetch(base + path.split("/").map(encodeURIComponent).join("/"), {
      cache: "no-cache",
    });
    if (!response.ok || response.headers.get("content-type")?.includes("text/html"))
      throw new Error(
        `Cannot load game data ${path} (${response.status}); run pnpm library:game-data`,
      );
    return response;
  }
  const index = await (await read("index.json")).json();
  if (index?.version !== 1 || !Array.isArray(index.files))
    throw new Error("Invalid game data index");
  const directories = new Map<string, Map<string, "file" | "directory">>([["", new Map()]]);
  for (const path of index.files) {
    if (typeof path !== "string") throw new Error("Invalid game data index path");
    const parts = path.split("/").map(segment);
    let prefix = "";
    for (const [i, name] of parts.entries()) {
      const kind = i === parts.length - 1 ? "file" : "directory";
      const entries = directories.get(prefix)!;
      if (entries.has(name) && entries.get(name) !== kind)
        throw new Error(`Conflicting game data path: ${path}`);
      entries.set(name, kind);
      prefix += name + "/";
      if (kind === "directory" && !directories.has(prefix)) directories.set(prefix, new Map());
    }
  }
  const missing = (path: string) => new DOMException(`Missing game data: ${path}`, "NotFoundError");
  const readonly = () => {
    throw new DOMException("Game data is read-only", "NotAllowedError");
  };
  function directory(prefix: string): FileSystemDirectoryHandle {
    return {
      kind: "directory",
      name: prefix.split("/").at(-2) ?? "HTTP game data",
      async getDirectoryHandle(name: string, options?: FileSystemGetDirectoryOptions) {
        if (options?.create) readonly();
        if (directories.get(prefix)!.get(segment(name)) !== "directory")
          throw missing(prefix + name);
        return directory(prefix + name + "/");
      },
      async getFileHandle(name: string, options?: FileSystemGetFileOptions) {
        if (options?.create) readonly();
        if (directories.get(prefix)!.get(segment(name)) !== "file") throw missing(prefix + name);
        return {
          kind: "file",
          name,
          async getFile() {
            const response = await read(prefix + name);
            return new File([await response.arrayBuffer()], name, {
              type: response.headers.get("content-type") ?? "",
            });
          },
          createWritable: readonly,
        } as unknown as FileSystemFileHandle;
      },
      async *entries() {
        for (const [name, kind] of directories.get(prefix)!)
          yield [
            name,
            kind === "directory"
              ? directory(prefix + name + "/")
              : await directory(prefix).getFileHandle(name),
          ];
      },
      removeEntry: readonly,
    } as unknown as FileSystemDirectoryHandle;
  }
  const result = await scanDatadir(directory(""));
  result.missionEntries = await loadMissionCatalog(result);
  return result;
}
