import { For, Show, createEffect, createSignal, onCleanup } from "solid-js";
import type { ProjectionAssetEntry } from "@rle/shared";
import AssetPreview, { AssetPreviewRenderer } from "./AssetPreview";
import { ASSET_DRAG_TYPE, assetType, assetTags, filterAssets } from "./asset-library";

export default function AssetLibrary(props: {
  root: FileSystemDirectoryHandle | null;
  entries: ProjectionAssetEntry[];
  loading: boolean;
  error: string;
  canInsert: boolean;
  collapsed: boolean;
  onToggle: () => void;
  onPreload: (entry: ProjectionAssetEntry) => void;
  onDragStart: (entry: ProjectionAssetEntry) => void;
  onDragReturn: () => void;
  onAdd: (entry: ProjectionAssetEntry) => void;
  onDragEnd: () => void;
}) {
  const [search, setSearch] = createSignal("");
  const [type, setType] = createSignal("");
  const [source, setSource] = createSignal("");
  createEffect(() => props.root, () => { setType(""); setSource(""); setSearch(""); });
  const renderer = new AssetPreviewRenderer();
  onCleanup(() => renderer.dispose());
  const filtered = () => filterAssets(props.entries, search(), type(), source());
  return <aside class="shared-library" onDragEnter={props.onDragReturn}
    onDragOver={event => { if (event.dataTransfer?.types.includes(ASSET_DRAG_TYPE)) { event.preventDefault(); event.dataTransfer.dropEffect = 'none'; } }}
    onDrop={event => { if (event.dataTransfer?.types.includes(ASSET_DRAG_TYPE)) { event.preventDefault(); props.onDragEnd(); } }}>
    <header class="library-heading">
      <button onClick={props.onToggle} aria-expanded={props.collapsed ? 'false' : 'true'} aria-controls="asset-library-content"
        aria-label={props.collapsed ? 'Show asset library' : 'Hide asset library'}
        title={props.collapsed ? 'Show asset library' : 'Hide asset library'}>{props.collapsed ? '→' : '←'}</button>
      <h2>Asset library</h2>
    </header>
    <div id="asset-library-content" class="library-content" hidden={props.collapsed}>
    <div class="library-filters">
      <input class="search" aria-label="Find assets" placeholder="Search assets or tags…" value={search()}
        onInput={event => setSearch(event.currentTarget.value)} />
      <label>Asset type<select aria-label="Asset type" value={type()} onChange={event => setType(event.currentTarget.value)}>
        <option value="">All types</option>
        <For each={[...new Set(props.entries.map(assetType))].sort()}>{value => <option value={value}>{value}</option>}</For>
      </select></label>
      <label>Source level<select aria-label="Source level" value={source()} onChange={event => setSource(event.currentTarget.value)}>
        <option value="">All levels</option>
        <For each={[...new Set(props.entries.map(entry => entry.source_map))].sort()}>{value => <option value={value}>{value}</option>}</For>
      </select></label>
    </div>
    <p class="library-summary" aria-live="polite">{filtered().length} of {props.entries.length} assets · Hover to rotate</p>
    <Show when={!props.root}><p class="hint">Waiting for assets…</p></Show>
    <Show when={props.loading}><p class="hint">Loading shared library…</p></Show>
    <Show when={props.error}><p class="library-error" role="alert">{props.error}</p></Show>
    <Show when={!props.loading && props.root && !props.error && !filtered().length}>
      <p class="hint">{props.entries.length ? "No assets match these filters." : "No published 3D assets in this library."}</p>
    </Show>
    <div class="asset-grid">
      <For each={filtered()}>{entry =>
        <article class="asset-card" draggable={props.canInsert && entry.editor_usage !== "map-background" ? "true" : "false"}
          onPointerEnter={() => { if (props.canInsert && entry.editor_usage !== 'map-background') props.onPreload(entry); }}
          onFocus={() => { if (props.canInsert && entry.editor_usage !== 'map-background') props.onPreload(entry); }}
          onDragStart={event => {
            if (!props.canInsert || entry.editor_usage === "map-background") { event.preventDefault(); return; }
            event.dataTransfer!.setData(ASSET_DRAG_TYPE, entry.id);
            event.dataTransfer!.effectAllowed = "copy";
            const image = document.createElement('canvas'); image.width = image.height = 1;
            event.dataTransfer!.setDragImage(image, 0, 0);
            props.onDragStart(entry);
          }} onDragEnd={props.onDragEnd}>
          <AssetPreview entry={entry} root={props.root!} renderer={renderer} />
          <div class="asset-card-info"><strong title={entry.name}>{entry.name}</strong>
            <div class="asset-tags"><For each={assetTags(entry)}>{tag => <span>{tag}</span>}</For></div>
            <button disabled={!props.canInsert || entry.editor_usage === "map-background"}
              onClick={() => props.onAdd(entry)} aria-label={`Add ${entry.name}`}>
              {entry.editor_usage === "map-background" ? "Map background" : "Add to scene"}
            </button>
          </div>
        </article>
      }</For>
    </div>
    <footer>{props.canInsert ? "Drag an asset into the scene to place it." : "Open a level to place assets."}</footer>
    </div>
  </aside>;
}
