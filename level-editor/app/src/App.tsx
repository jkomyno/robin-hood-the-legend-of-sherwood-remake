// Published assets load over HTTP; map edits stay in browser storage.
import { Show, createEffect, createSignal, onCleanup } from "solid-js";
import {
  getStoredDatadirHandle,
  pickDatadir,
  requestDatadirPermission,
  restoreDatadir,
} from "./fs";
import { scanDatadir, type DatadirIndex } from "./datadir";
import Editor3D, { type LibraryRef } from "./Editor3D";
import { connectionAttempts, connectLatest } from "./connection-attempt";
import { openHttpLibrary } from './http-library.ts';
import { loadMissionCatalog } from './mission-catalog.ts';

export default function App() {
  const [index, setIndex] = createSignal<DatadirIndex | null>(null);
  const [needsReconnect, setNeedsReconnect] = createSignal(false);
  // wrapped: a directory handle is async-iterable, and Solid 2 flattens iterables returned by effect computes
  const [library, setLibrary] = createSignal<LibraryRef | null>(null);
  const [error, setError] = createSignal<string | null>(null);
  const [status, setStatus] = createSignal<string | null>(null);
  const datadirAttempts = connectionAttempts();
  const libraryAttempts = connectionAttempts();
  onCleanup(() => {
    datadirAttempts.dispose();
    libraryAttempts.dispose();
  });

  async function openRoot(
    handle: FileSystemDirectoryHandle,
    current: () => boolean,
  ) {
    if (!current()) return;
    setStatus("scanning datadir…");
    const next = await scanDatadir(handle);
    next.missionEntries = await loadMissionCatalog(next);
    if (!current()) return;
    setIndex(next);
    setNeedsReconnect(false);
  }

  const connectDatadir = (operation: (current: () => boolean) => Promise<void>) =>
    connectLatest(
      datadirAttempts,
      async (current) => {
        setError(null);
        setStatus(null);
        await operation(current);
      },
      (error) => setError(String(error)),
      () => setStatus(null),
    );
  const connectLibrary = (operation: (current: () => boolean) => Promise<void>) =>
    connectLatest(
      libraryAttempts,
      async (current) => {
        setError(null);
        await operation(current);
      },
      (error) => setError(String(error)),
    );

  // Restore optional game data and connect the published library on startup.
  createEffect(
    () => undefined,
    () => {
      void connectDatadir(async (current) => {
        const restored = await restoreDatadir();
        if (!current()) return;
        if (restored) await openRoot(restored, current);
        else {
          const stored = await getStoredDatadirHandle();
          if (current()) setNeedsReconnect(stored !== null);
        }
      });
      void connectLibrary(async (current) => {
        const lib = await openHttpLibrary();
        if (!current()) return;
        setLibrary(lib);
      });
    },
  );

  function onPick() {
    return connectDatadir(async (current) => {
      const handle = await pickDatadir(current);
      if (current()) await openRoot(handle, current);
    });
  }
  function onReconnect() {
    return connectDatadir(async (current) => {
      const handle = await getStoredDatadirHandle();
      if (!current() || !handle) return;
      const granted = await requestDatadirPermission(handle);
      if (current() && granted) await openRoot(handle, current);
    });
  }

  return (
    <div class="app editor-app">
      <header class="topbar">
        <h1>Sherwood <span class="brand-subtitle">Level editor</span></h1>
        <Show
          when={index()}
          fallback={
            <button
              class="connect"
              title="Optional, read-only game data for mission previews, sprites, and reference terrain"
              onClick={needsReconnect() ? onReconnect : onPick}
            >
              {needsReconnect()
                ? "Reconnect game data"
                : "Connect game data…"}
            </button>
          }
        >
          {(idx) => (
            <span class="connected">
              Game data · {idx().maps.size} maps{" "}
              <button onClick={onPick}>change</button>
            </span>
          )}
        </Show>
        <span class="spacer" />
        <Show when={status()}>{(s) => <span class="busy">{s()}</span>}</Show>
        <Show when={error()}>
          {(e) => (
            <span class="error" role="alert">
              {e()} <button aria-label="Dismiss error" onClick={() => setError(null)}>×</button>
            </span>
          )}
        </Show>
      </header>
      <Editor3D
        index={index}
        library={library}
        onError={setError}
        onStatus={setStatus}
      />
    </div>
  );
}
