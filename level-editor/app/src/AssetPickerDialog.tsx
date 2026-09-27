import { For, Show, createSignal, onCleanup } from "solid-js";
import type { ProjectionAssetEntry } from "@rle/shared";
import AssetPreview, { AssetPreviewRenderer } from "./AssetPreview";

/** The same preview cards for wall strips and matching corner models. */
export default function AssetPickerDialog(props: {
  title: string;
  root: FileSystemDirectoryHandle;
  entries: ProjectionAssetEntry[];
  selected?: string;
  emptyLabel?: string;
  onSelect(id: string): void;
  onClose(): void;
}) {
  const renderer = new AssetPreviewRenderer();
  onCleanup(() => renderer.dispose());
  const [query, setQuery] = createSignal("");
  const [map, setMap] = createSignal("");
  const entries = () =>
    props.entries.filter(
      (entry) =>
        (!map() || entry.source_map === map()) &&
        `${entry.name} ${entry.source_map}`.toLowerCase().includes(query().toLowerCase()),
    );
  return (
    <dialog
      class="asset-picker-dialog"
      aria-label={props.title}
      ref={(dialog) =>
        queueMicrotask(() => {
          if (dialog.isConnected) dialog.showModal();
        })
      }
      onCancel={(event) => {
        event.preventDefault();
        props.onClose();
      }}
    >
      <div class="asset-picker-heading">
        <h2>{props.title}</h2>
        <button aria-label="Close asset picker" onClick={() => props.onClose()}>
          ×
        </button>
      </div>
      <div class="asset-picker-filters">
        <input
          aria-label="Search assets"
          placeholder="Search…"
          value={query()}
          onInput={(event) => setQuery(event.currentTarget.value)}
        />
        <select
          aria-label="Source map"
          value={map()}
          onChange={(event) => setMap(event.currentTarget.value)}
        >
          <option value="">All maps</option>
          <For each={[...new Set(props.entries.map((entry) => entry.source_map))].sort()}>
            {(name) => <option value={name}>{name}</option>}
          </For>
        </select>
      </div>
      <Show when={props.emptyLabel}>
        <button class="asset-picker-none" onClick={() => props.onSelect("")}>
          {props.emptyLabel}
        </button>
      </Show>
      <div class="asset-grid">
        <For each={entries()}>
          {(entry) => (
            <button
              class={props.selected === entry.id ? "asset-card selected" : "asset-card"}
              onClick={() => props.onSelect(entry.id)}
            >
              <AssetPreview entry={entry} root={props.root} renderer={renderer} />
              <span class="asset-card-info">
                <strong>{entry.name}</strong>
                <small>{entry.source_map}</small>
              </span>
            </button>
          )}
        </For>
      </div>
      <Show when={!entries().length}>
        <p>No matching assets.</p>
      </Show>
    </dialog>
  );
}
