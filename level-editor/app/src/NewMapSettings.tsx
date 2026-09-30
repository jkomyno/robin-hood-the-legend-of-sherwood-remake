import { For, createSignal } from "solid-js";
import { MAP_SIZE_PRESETS, type NewMapOptions } from "./workspace";

export default function NewMapSettings(props: {
  value: NewMapOptions;
  onChange(value: NewMapOptions): void;
}) {
  const [chosenPreset, setChosenPreset] = createSignal("");
  const preset = () =>
    (
      MAP_SIZE_PRESETS.find(
        (entry) =>
          entry.name === chosenPreset() &&
          entry.size.every((value, index) => value === props.value.size[index]),
      ) ??
      MAP_SIZE_PRESETS.find((entry) =>
        entry.size.every((value, index) => value === props.value.size[index]),
      )
    )?.name ?? "";
  function dimension(index: number, value: number) {
    const size: [number, number] = [...props.value.size];
    size[index] = value;
    props.onChange({ ...props.value, size });
  }
  return (
    <div class="new-map-settings">
      <label>
        Map size preset
        <select
          aria-label="Map size preset"
          value={preset()}
          onChange={(event) => {
            const choice = MAP_SIZE_PRESETS.find(
              (entry) => entry.name === event.currentTarget.value,
            );
            if (choice) {
              setChosenPreset(choice.name);
              props.onChange({ ...props.value, size: [...choice.size] });
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
      <For each={["Width", "Height"]}>
        {(label, index) => (
          <label>
            {label} (px)
            <input
              type="number"
              aria-label={`Map ${label.toLowerCase()}`}
              required
              min="1"
              step="1"
              value={props.value.size[index()]}
              onInput={(event) => dimension(index(), event.currentTarget.valueAsNumber)}
            />
          </label>
        )}
      </For>
      <label>
        Grid spacing (px)
        <input
          type="number"
          aria-label="Grid spacing"
          required
          min="1"
          step="1"
          value={props.value.spacing}
          onInput={(event) =>
            props.onChange({ ...props.value, spacing: event.currentTarget.valueAsNumber })
          }
        />
      </label>
      <label>
        Initial elevation
        <input
          type="number"
          aria-label="Initial elevation"
          required
          step="any"
          value={props.value.height}
          onInput={(event) =>
            props.onChange({ ...props.value, height: event.currentTarget.valueAsNumber })
          }
        />
      </label>
      <p class="hint">Resize the workspace later without deleting terrain or assets.</p>
    </div>
  );
}
