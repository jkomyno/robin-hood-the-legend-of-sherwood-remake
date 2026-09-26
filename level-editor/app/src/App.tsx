// Published assets load over HTTP; map edits stay in browser storage.
import { Show, createEffect, createSignal, onCleanup } from "solid-js";
import type { DatadirIndex } from "./datadir";
import { openHttpGameData } from "./http-game-data.ts";
import Editor3D, { type LibraryRef } from "./Editor3D";
import { connectionAttempts, connectLatest } from "./connection-attempt";
import { openHttpLibrary } from "./http-library.ts";

export default function App() {
  const [index, setIndex] = createSignal<DatadirIndex | null>(null);
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

  // Load game data and published assets over HTTP on startup.
  createEffect(
    () => undefined,
    () => {
      void connectDatadir(async (current) => {
        const next = await openHttpGameData();
        if (current()) setIndex(next);
      });
      void connectLibrary(async (current) => {
        const lib = await openHttpLibrary();
        if (!current()) return;
        setLibrary(lib);
      });
    },
  );

  return (
    <div class="app editor-app">
      <Editor3D
        index={index}
        library={library}
        onError={setError}
        onStatus={setStatus}
        toolbarStart={() => <h1 title="Level editor">Sherwood</h1>}
        toolbarEnd={() => (
          <>
            <Show when={status()}>{(s) => <span class="busy">{s()}</span>}</Show>
            <Show when={error()}>
              {(e) => (
                <span class="error" role="alert">
                  {e()}{" "}
                  <button aria-label="Dismiss error" onClick={() => setError(null)}>
                    ×
                  </button>
                </span>
              )}
            </Show>
          </>
        )}
      />
    </div>
  );
}
