import { For, Show, createMemo, createSignal, createUniqueId } from "solid-js";
import {
  terrainMaterials,
  validateCustomTerrainMaterials,
  type CustomTerrainMaterial,
} from "@rle/shared";

export interface MaterialPickerProps {
  value: string;
  onChange(id: string): void;
  customMaterials: readonly CustomTerrainMaterial[];
  onCustomMaterialsChange(materials: CustomTerrainMaterial[]): void;
  label?: string;
  disabled?: boolean;
}

/** Shared catalog chooser. Creating a custom material adds it to the map catalog. */
export default function MaterialPicker(props: MaterialPickerProps) {
  const id = createUniqueId();
  const [search, setSearch] = createSignal("");
  const [name, setName] = createSignal("");
  const [color, setColor] = createSignal("#8c7853");
  const [feedback, setFeedback] = createSignal("");
  const [error, setError] = createSignal("");
  const materials = createMemo(() => [...terrainMaterials, ...props.customMaterials]);
  const matches = createMemo(() => {
    const query = search().trim().toLocaleLowerCase();
    return materials().filter((material) =>
      `${material.name} ${material.id} ${"category" in material ? material.category : "custom"}`
        .toLocaleLowerCase()
        .includes(query),
    );
  });
  const options = createMemo(() => {
    const results = matches();
    const current = materials().find((material) => material.id === props.value);
    return current && !results.some((material) => material.id === current.id)
      ? [current, ...results]
      : results;
  });
  const selected = createMemo(() => materials().find((material) => material.id === props.value));

  function addCustomMaterial() {
    setFeedback("");
    setError("");
    const displayName = name().trim();
    if (!displayName) {
      setError("Enter a material name.");
      return;
    }
    const stem = `custom_${
      displayName
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "") || "material"
    }`;
    const ids = new Set(materials().map((material) => material.id));
    let newId = stem;
    for (let suffix = 2; ids.has(newId); suffix++) newId = `${stem}_${suffix}`;
    const next = [...props.customMaterials, { id: newId, name: displayName, color: color() }];
    try {
      validateCustomTerrainMaterials(next);
      props.onCustomMaterialsChange(next);
      setSearch(displayName);
      setName("");
      setFeedback(`Added ${displayName}. Select it above to apply it.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  return (
    <fieldset class="material-picker" disabled={props.disabled}>
      <legend>{props.label ?? "Material"}</legend>
      <label for={`${id}-search`}>Search materials</label>
      <input
        id={`${id}-search`}
        type="search"
        placeholder="Name, category or ID"
        value={search()}
        onInput={(event) => setSearch(event.currentTarget.value)}
      />
      <label for={`${id}-select`}>{props.label ?? "Material"}</label>
      <select
        id={`${id}-select`}
        value={props.value}
        onChange={(event) => props.onChange(event.currentTarget.value)}
      >
        <For each={options()}>
          {(material) => <option value={material.id}>{material.name}</option>}
        </For>
      </select>
      <Show when={search().trim() && matches().length === 0}>
        <p class="hint">No matching materials. The current selection remains available.</p>
      </Show>
      <Show when={selected()}>
        {(material) => (
          <p class="hint">
            <span
              aria-hidden="true"
              style={{
                display: "inline-block",
                width: "1em",
                height: "1em",
                "margin-right": "0.4em",
                background: material().color,
                border: "1px solid currentColor",
              }}
            />
            {material().name} · {material().id}
          </p>
        )}
      </Show>
      <details>
        <summary>Add custom material</summary>
        <label for={`${id}-name`}>Material name</label>
        <input
          id={`${id}-name`}
          type="text"
          value={name()}
          onInput={(event) => setName(event.currentTarget.value)}
        />
        <label for={`${id}-color`}>Material color</label>
        <input
          id={`${id}-color`}
          type="color"
          value={color()}
          onInput={(event) => setColor(event.currentTarget.value)}
        />
        <button type="button" onClick={addCustomMaterial}>
          Add to map materials
        </button>
        <Show when={error()}>
          <p role="alert">{error()}</p>
        </Show>
        <Show when={feedback()}>
          <p role="status">{feedback()}</p>
        </Show>
      </details>
    </fieldset>
  );
}
