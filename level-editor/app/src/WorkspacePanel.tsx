import { For, createEffect, createSignal } from "solid-js";
import type { Level3D } from "@rle/shared";
import { MAP_SIZE_PRESETS, resizeWorkspace } from "./workspace";

export default function WorkspacePanel(props: {
  document: () => Level3D | null;
  commit(document: Level3D): void;
  onError(message: string): void;
}) {
  const [width, setWidth] = createSignal(1920);
  const [height, setHeight] = createSignal(1088);
  const [chosenPreset, setChosenPreset] = createSignal("");
  createEffect(
    () => props.document()?.size,
    (size) => {
      setWidth(size?.[0] ?? 1920);
      setHeight(size?.[1] ?? 1088);
    },
  );
  const preset = () =>
    (
      MAP_SIZE_PRESETS.find(
        (entry) =>
          entry.name === chosenPreset() && entry.size[0] === width() && entry.size[1] === height(),
      ) ?? MAP_SIZE_PRESETS.find((entry) => entry.size[0] === width() && entry.size[1] === height())
    )?.name ?? "";
  function resize() {
    const document = props.document();
    if (!document) return;
    try {
      props.commit(resizeWorkspace(document, [width(), height()]));
    } catch (error) {
      props.onError(error instanceof Error ? error.message : String(error));
    }
  }
  return (
    <section class="view-settings workspace-settings">
      <h2>Workspace</h2>
      <fieldset disabled={!props.document()}>
        <label>
          Reference map
          <select
            aria-label="Workspace size preset"
            value={preset()}
            onChange={(event) => {
              const choice = MAP_SIZE_PRESETS.find(
                (entry) => entry.name === event.currentTarget.value,
              );
              if (choice) {
                setChosenPreset(choice.name);
                setWidth(choice.size[0]);
                setHeight(choice.size[1]);
              }
            }}
          >
            <option value="">Custom</option>
            <For each={MAP_SIZE_PRESETS}>
              {(entry) => (
                <option value={entry.name}>
                  {entry.name} · {entry.size[0]} × {entry.size[1]} px
                </option>
              )}
            </For>
          </select>
        </label>
        <label>
          Width (px)
          <input
            type="number"
            aria-label="Workspace width"
            min="1"
            step="1"
            value={width()}
            onInput={(event) => setWidth(event.currentTarget.valueAsNumber)}
          />
        </label>
        <label>
          Height (px)
          <input
            type="number"
            aria-label="Workspace height"
            min="1"
            step="1"
            value={height()}
            onInput={(event) => setHeight(event.currentTarget.valueAsNumber)}
          />
        </label>
        <button type="button" onClick={resize}>
          Resize workspace
        </button>
      </fieldset>
      <p class="hint">
        Content outside the boundary stays editable and is never deleted. Enlarging adds ground
        where needed.
      </p>
    </section>
  );
}
