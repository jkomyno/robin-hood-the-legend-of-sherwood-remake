/** Use the same publication boundary as the Python/Blender catalog writers. */
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const script = fileURLToPath(new URL("../../refinement/asset_index.py", import.meta.url));

export function validateAssetIndex(
  root: string,
  index: unknown,
  files: Record<string, string> = {},
): void {
  execFileSync("python3", [script, root, "--check", "--files", JSON.stringify(files)], {
    input: JSON.stringify(index),
    stdio: ["pipe", "pipe", "pipe"],
  });
}

export function writeAssetIndex(root: string, index: unknown): void {
  execFileSync("python3", [script, root], {
    input: JSON.stringify(index, null, 2) + "\n",
    stdio: ["pipe", "pipe", "pipe"],
  });
}
