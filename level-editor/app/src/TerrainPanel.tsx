import ScrubNumber from "./ScrubNumber";
import type { EditorViewport } from "./editor-viewport";
import { For, Show, createSignal, createEffect, onCleanup, untrack } from "solid-js";
import { parseLevel3D, type GroundRegion, type Level3D } from "@rle/shared";

export default function TerrainPanel(props: {
  document: () => Level3D | null;
  commit(document: Level3D): void;
  onError(message: string): void;
  disabled?: boolean;
  active?: boolean;
  viewport: EditorViewport;
}) {
  const [selected, setSelected] = createSignal("");
  const region = () => props.document()?.terrain?.find((r) => r.id === selected());
  createEffect(
    () => ({
      region: region(),
      camera: props.document()?.camera,
      enabled: props.active !== false && !props.disabled,
    }),
    ({ region, camera, enabled }) => {
      untrack(() =>
        props.viewport.setTerrainEdit(
          region && camera && enabled
            ? {
                region,
                camera,
                commit: (next) => change({ bounds: next.bounds, height: next.height }),
                deselect: () => setSelected(""),
              }
            : null,
        ),
      );
    },
  );
  createEffect(
    () => props.active !== false && !props.disabled,
    (enabled) => {
      untrack(() => props.viewport.setTerrainSelectionHandler(enabled ? setSelected : null));
    },
  );
  onCleanup(() => {
    props.viewport.setTerrainSelectionHandler(null);
    props.viewport.setTerrainEdit(null);
  });
  function preview(patch: Partial<GroundRegion>) {
    const r = region();
    if (r) props.viewport.previewTerrain({ ...r, ...patch });
  }
  const cancelPreview = () => props.viewport.previewTerrain(null);
  function setBound(index: number, value: number, commit: boolean) {
    const r = region();
    if (!r) return;
    const bounds = [...r.bounds] as GroundRegion["bounds"];
    bounds[index] = value;
    if (commit) {
      cancelPreview();
      change({ bounds });
    } else preview({ bounds });
  }
  function publish(terrain: GroundRegion[]) {
    const document = props.document();
    if (!document) return;
    try {
      const next = { ...document, terrain };
      parseLevel3D(next);
      props.commit(next);
    } catch (error) {
      props.onError(String(error));
    }
  }
  function change(patch: Partial<GroundRegion>) {
    publish(
      (props.document()?.terrain ?? []).map((r) => (r.id === selected() ? { ...r, ...patch } : r)),
    );
  }
  function add() {
    const document = props.document();
    if (!document) return;
    const id = "ground-" + crypto.randomUUID();
    const bounds = document.exportBounds ?? [0, 0, ...(document.size ?? [1200, 900])];
    publish([
      ...(document.terrain ?? []),
      {
        id,
        name: "Ground",
        bounds: [...bounds] as GroundRegion["bounds"],
        height: 0,
        material: "grass",
      },
    ]);
    setSelected(id);
  }
  return (
    <section class="view-settings terrain-settings">
      <h2>Terrain</h2>
      <p class="hint">
        Create continuous ground, then choose its material and elevation. Later regions replace
        earlier ones. Water is not walkable.
      </p>
      <fieldset disabled={props.disabled || !props.document()}>
        <button onClick={add}>Add ground region</button>
        <label>
          Ground region
          <select
            aria-label="Ground region"
            value={selected()}
            onChange={(e) => setSelected(e.currentTarget.value)}
          >
            <option value="">Choose a region</option>
            <For each={props.document()?.terrain ?? []}>
              {(r) => (
                <option value={r.id}>
                  {r.name} · {Math.round(r.height * 100) / 100}
                </option>
              )}
            </For>
          </select>
        </label>
        <Show when={region()}>
          {(current) => (
            <>
              <label>
                Name
                <input
                  value={current().name}
                  onChange={(e) => change({ name: e.currentTarget.value })}
                />
              </label>
              <label>
                Material
                <select
                  aria-label="Terrain material"
                  value={current().material}
                  onChange={(e) =>
                    change({ material: e.currentTarget.value as GroundRegion["material"] })
                  }
                >
                  <option value="grass">Grass</option>
                  <option value="dirt">Dirt</option>
                  <option value="paved">Paved</option>
                  <option value="water">Water</option>
                </select>
              </label>
              <p class="hint">
                Drag a gold corner to resize, or use the move gizmo to move the region and change
                its elevation. Escape cancels a drag.
              </p>
              <ScrubNumber
                label="Terrain elevation"
                value={current().height}
                step={1}
                onPreview={(height) => preview({ height })}
                onCommit={(height) => {
                  cancelPreview();
                  change({ height });
                }}
                onCancel={cancelPreview}
              />
              <details>
                <summary>Position and size</summary>
                <For each={["X", "Y", "Width", "Depth"]}>
                  {(label, i) => (
                    <ScrubNumber
                      label={`Terrain ${label}`}
                      value={current().bounds[i()]!}
                      step={1}
                      min={i() > 1 ? 1 : undefined}
                      onPreview={(v) => setBound(i(), v, false)}
                      onCommit={(v) => setBound(i(), v, true)}
                      onCancel={cancelPreview}
                    />
                  )}
                </For>
              </details>
              <button
                onClick={() => {
                  const r = current();
                  publish((props.document()?.terrain ?? []).filter((p) => p.id !== r.id).concat(r));
                }}
              >
                Bring region to top
              </button>
              <button
                onClick={() => {
                  publish((props.document()?.terrain ?? []).filter((p) => p.id !== selected()));
                  setSelected("");
                }}
              >
                Delete region
              </button>
              <p class="hint">
                New assets rest on this ground. Different elevations form separate walking areas;
                add stairs or connecting assets where characters should cross.
              </p>
            </>
          )}
        </Show>
      </fieldset>
    </section>
  );
}
