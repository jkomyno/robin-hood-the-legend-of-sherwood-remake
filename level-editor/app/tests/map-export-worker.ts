import { unzipSync } from "fflate";
import { MapExportWorker } from "../src/map-export-client.ts";
import { compileMap } from "../src/map-compile.ts";
import { joinedTransitionCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";

function check(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}
const worker = new MapExportWorker();
try {
  const { document: scene, assets } = joinedTransitionCompilerFixture();
  const bounds: [number, number, number, number] = [0, 0, 1024, 1024];
  let frames = 0;
  const heartbeat = () => {
    frames++;
    if (running) requestAnimationFrame(heartbeat);
  };
  let running = true;
  requestAnimationFrame(heartbeat);
  const compiled = await worker.compile(scene, bounds, assets);
  check(
    JSON.stringify(compiled) ===
      JSON.stringify(compileMap(scene, bounds, assets, { bestEffort: true })),
    "Worker compilation differs from synchronous compilation",
  );
  const color = new Uint8Array(1024 * 1024 * 4).fill(255);
  const depth = new Uint16Array(1024 * 1024);
  const patches = (compiled.descriptor.asset_geometry?.movement_transitions ?? [])
    .filter((transition) => transition.has_appearance)
    .map((transition) => transition.id);
  const bytes = await worker.package(
    compiled,
    { color, depth },
    patches.length
      ? [
          {
            bounds: [0, 0, 1, 1],
            patches,
            states: Array.from({ length: 2 ** patches.length }, () => ({
              color: new Uint8Array([255, 255, 255, 255]),
              depth: new Uint16Array([0]),
            })),
          },
        ]
      : [],
  );
  check(
    color.byteLength === 0 && depth.byteLength === 0,
    "Packaging copied its owned image buffers instead of transferring them",
  );
  running = false;
  check(frames > 0, "Browser did not repaint while the worker was busy");
  const zip = unzipSync(bytes);
  check(!!zip[`Data/Levels/${compiled.name}.level.json`], "ZIP omitted compiled geometry");
  check(
    Object.keys(zip).some((name) => name.startsWith("editor/")),
    "ZIP omitted editable scene",
  );
  let invalidRejected = false;
  try {
    await worker.compile(scene, [0, 0, -1, 1], assets);
  } catch {
    invalidRejected = true;
  }
  check(invalidRejected, "Worker swallowed a compilation error");
  const pending = worker.compile(scene, bounds, assets);
  worker.dispose();
  let cancelled = false;
  try {
    await pending;
  } catch {
    cancelled = true;
  }
  check(cancelled, "Disposed worker left an active request unresolved");
  document.getElementById("result")!.textContent =
    `PASS worker compile, ZIP, error, cancellation; ${frames} browser frames`;
} catch (error) {
  document.getElementById("result")!.textContent = `FAIL ${String(error)}`;
  throw error;
} finally {
  worker.dispose();
}
