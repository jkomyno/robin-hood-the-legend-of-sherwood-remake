import MaterialPicker from "./MaterialPicker";
import ScrubNumber from "./ScrubNumber";
import type { EditorViewport } from "./editor-viewport";
import { For, Show, createSignal, createEffect, onCleanup, untrack } from "solid-js";
import {
  parseLevel3D,
  createTerrainGrid,
  subdivideTerrainCells,
  type CustomTerrainMaterial,
  type TerrainGrid,
  type Level3D,
  type Vec3,
} from "@rle/shared";

export default function TerrainPanel(props: {
  document: () => Level3D | null;
  commit(document: Level3D): void;
  onError(message: string): void;
  disabled?: boolean;
  active?: boolean;
  viewport: EditorViewport;
}) {
  const [selected, setSelected] = createSignal("");
  const [cell, setCell] = createSignal("");
  const grid = () => props.document()?.terrain;
  const vertex = () => grid()?.vertices.find((v) => v.id === selected());
  const currentCell = () => grid()?.cells.find((c) => c.id === cell());
  function customMaterials(materials: CustomTerrainMaterial[]) {
    const document = props.document();
    if (!document) return;
    try {
      const next = { ...document, customMaterials: materials };
      parseLevel3D(next);
      props.commit(next);
    } catch (error) {
      props.onError(String(error));
    }
  }
  function publish(terrain: TerrainGrid) {
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
  createEffect(
    () => ({
      grid: grid(),
      camera: props.document()?.camera,
      selected: selected(),
      enabled: props.active !== false && !props.disabled,
    }),
    ({ grid, camera, selected, enabled }) =>
      untrack(() =>
        props.viewport.setTerrainEdit(
          grid && camera && enabled
            ? {
                grid,
                camera,
                selectedVertex: selected,
                selectVertex: setSelected,
                commit: publish,
                deselect: () => setSelected(""),
              }
            : null,
        ),
      ),
  );
  createEffect(
    () => props.active !== false && !props.disabled,
    (enabled) => untrack(() => props.viewport.setTerrainSelectionHandler(enabled ? setCell : null)),
  );
  onCleanup(() => {
    props.viewport.setTerrainSelectionHandler(null);
    props.viewport.setTerrainEdit(null);
  });
  const cancelPreview = () => props.viewport.previewTerrain(null);
  function position(axis: number, value: number, commit: boolean) {
    const g = grid(),
      v = vertex();
    if (!g || !v) return;
    const p = [...v.position] as Vec3;
    p[axis] = value;
    const next = {
      ...g,
      vertices: g.vertices.map((item) => (item.id === v.id ? { ...item, position: p } : item)),
    };
    if (commit) {
      cancelPreview();
      publish(next);
    } else {
      try {
        parseLevel3D({ ...props.document()!, terrain: next });
        props.viewport.previewTerrain(next);
      } catch {
        cancelPreview();
      }
    }
  }
  function changeCell(patch: Partial<NonNullable<Level3D["terrain"]>["cells"][number]>) {
    const g = grid();
    if (g)
      publish({
        ...g,
        vertices: patch.material
          ? g.vertices.map((v, i) =>
              currentCell()?.vertices.includes(i)
                ? { ...v, material: patch.material, materialMix: undefined }
                : v,
            )
          : g.vertices,
        cells: g.cells.map((c) => (c.id === cell() ? { ...c, ...patch } : c)),
      });
  }
  return (
    <section class="view-settings terrain-settings">
      <h2>Terrain grid</h2>
      <p class="hint">
        Select a vertex and drag to change elevation. Hold Shift while dragging to move it
        horizontally. Every vertex also has editable X, Y and Z values.
      </p>
      <fieldset disabled={props.disabled || !props.document()}>
        <Show
          when={grid()}
          fallback={
            <button
              onClick={() => {
                const d = props.document();
                if (d)
                  publish(createTerrainGrid(d.exportBounds ?? [0, 0, ...(d.size ?? [1200, 900])]));
              }}
            >
              Create terrain grid
            </button>
          }
        >
          <p class="hint">
            {grid()?.vertices.length} vertices · {grid()?.cells.length} cells. Click the ground to
            select a cell.
          </p>
          <Show when={vertex()}>
            {(v) => (
              <>
                <strong>Selected vertex</strong>
                <MaterialPicker
                  label="Vertex material"
                  value={
                    v().material ??
                    Object.entries(v().materialMix ?? {}).sort((a, b) => b[1] - a[1])[0]?.[0] ??
                    "grass_short"
                  }
                  customMaterials={props.document()?.customMaterials ?? []}
                  onCustomMaterialsChange={customMaterials}
                  onChange={(material) => {
                    const g = grid();
                    if (g)
                      publish({
                        ...g,
                        vertices: g.vertices.map((item) =>
                          item.id === v().id ? { ...item, material, materialMix: undefined } : item,
                        ),
                      });
                  }}
                />
                <For each={["X", "Y", "Z"]}>
                  {(label, i) => (
                    <ScrubNumber
                      label={`Vertex ${label}`}
                      value={v().position[i()]!}
                      step={1}
                      onPreview={(value) => position(i(), value, false)}
                      onCommit={(value) => position(i(), value, true)}
                      onCancel={cancelPreview}
                    />
                  )}
                </For>
              </>
            )}
          </Show>
          <Show when={currentCell()}>
            {(c) => (
              <>
                <MaterialPicker
                  label="Terrain material"
                  value={c().material}
                  customMaterials={props.document()?.customMaterials ?? []}
                  onCustomMaterialsChange={customMaterials}
                  onChange={(material) => changeCell({ material })}
                />
                <label>
                  Walkability
                  <select
                    value={c().walkable === undefined ? "auto" : String(c().walkable)}
                    onChange={(e) =>
                      changeCell({
                        walkable:
                          e.currentTarget.value === "auto"
                            ? undefined
                            : e.currentTarget.value === "true",
                      })
                    }
                  >
                    <option value="auto">Use material</option>
                    <option value="true">Walkable</option>
                    <option value="false">Blocked</option>
                  </select>
                </label>
                <button
                  onClick={() => {
                    const g = grid();
                    if (g) {
                      try {
                        publish(subdivideTerrainCells(g, [cell()]));
                        setCell("");
                      } catch (error) {
                        props.onError(String(error));
                      }
                    }
                  }}
                >
                  Subdivide selected cell
                </button>
              </>
            )}
          </Show>
        </Show>
      </fieldset>
    </section>
  );
}
