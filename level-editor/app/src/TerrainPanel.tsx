import { For, Show, createSignal } from "solid-js";
import { parseLevel3D, type GroundRegion, type Level3D } from "@rle/shared";

export default function TerrainPanel(props: {
  document: () => Level3D | null;
  commit(document: Level3D): void;
  onError(message: string): void;
  disabled?: boolean;
}) {
  const [selected, setSelected] = createSignal("");
  const region = () => props.document()?.terrain?.find((r) => r.id === selected());
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
                  {r.name} · {r.height}
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
                  <option value="water">Water</option>
                </select>
              </label>
              <label>
                Elevation
                <input
                  aria-label="Terrain elevation"
                  type="number"
                  value={current().height}
                  onChange={(e) => change({ height: e.currentTarget.valueAsNumber })}
                />
              </label>
              <div class="spline-coordinates">
                <For each={["X", "Y", "Width", "Depth"]}>
                  {(label, i) => (
                    <label>
                      {label}
                      <input
                        aria-label={`Terrain ${label}`}
                        type="number"
                        min={i() > 1 ? 1 : undefined}
                        value={current().bounds[i()]}
                        onChange={(e) => {
                          const bounds = [...current().bounds] as GroundRegion["bounds"];
                          bounds[i()] = e.currentTarget.valueAsNumber;
                          change({ bounds });
                        }}
                      />
                    </label>
                  )}
                </For>
              </div>
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
