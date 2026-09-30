import { For, Show, createEffect, createSignal, onCleanup, untrack } from "solid-js";
import { parseLevel3D, type Level3D, type Vec3 } from "@rle/shared";
import type { EditorViewport } from "./editor-viewport.ts";

export default function MissionPanel(props: {
  document(): Level3D | null;
  commit(document: Level3D): void;
  onError(message: string): void;
  active: boolean;
  viewport: EditorViewport;
}) {
  const [selected, setSelected] = createSignal("");
  const [placing, setPlacing] = createSignal<"pc" | "npc" | "move" | null>(null);
  const entries = () => [
    ...(props.document()?.mission?.spawnPoints ?? []).map((entry) => ({
      ...entry,
      kind: "pc" as const,
    })),
    ...(props.document()?.mission?.soldiers ?? []).map((entry) => ({
      ...entry,
      kind: "npc" as const,
    })),
  ];
  const current = () => entries().find((entry) => entry.id === selected());
  const mission = () =>
    props.document()?.mission ?? { version: 1 as const, spawnPoints: [], soldiers: [] };
  function publish(next: NonNullable<Level3D["mission"]>) {
    const document = props.document();
    if (!document) return;
    try {
      const updated = { ...document, mission: next };
      parseLevel3D(updated);
      props.commit(updated);
    } catch (error) {
      props.onError(String(error));
    }
  }
  function change(patch: { name?: string; position?: Vec3; direction?: number }) {
    const value = mission();
    publish({
      ...value,
      spawnPoints: value.spawnPoints.map((entry) =>
        entry.id === selected() ? { ...entry, ...patch } : entry,
      ),
      soldiers: value.soldiers.map((entry) =>
        entry.id === selected() ? { ...entry, ...patch } : entry,
      ),
    });
  }
  function place(position: Vec3) {
    const kind = placing();
    if (!kind) return;
    if (kind === "move") change({ position });
    else {
      const id = `${kind}-${crypto.randomUUID()}`;
      const base = { id, name: kind === "pc" ? "PC spawn" : "Soldier", position, direction: 0 };
      const value = mission();
      publish(
        kind === "pc"
          ? { ...value, spawnPoints: [...value.spawnPoints, { ...base, profile: 0 }] }
          : {
              ...value,
              soldiers: [...value.soldiers, { ...base, profile: "guard_a01", allegiance: 1 }],
            },
      );
      setSelected(id);
    }
    setPlacing(null);
  }
  createEffect(
    () => ({
      active: props.active,
      document: props.document(),
      selected: selected(),
      placing: placing(),
    }),
    ({ active, document, selected, placing }) => {
      untrack(() =>
        props.viewport.setMissionEdit(
          active && document
            ? {
                selected,
                select: setSelected,
                ...(placing ? { place } : {}),
              }
            : null,
        ),
      );
      if (!active) setPlacing(null);
    },
  );
  onCleanup(() => props.viewport.setMissionEdit(null));
  const cancelPlacement = (event: KeyboardEvent) => {
    if (props.active && event.key === "Escape") setPlacing(null);
  };
  window.addEventListener("keydown", cancelPlacement);
  onCleanup(() => window.removeEventListener("keydown", cancelPlacement));
  function remove() {
    const value = mission();
    publish({
      ...value,
      spawnPoints: value.spawnPoints.filter((entry) => entry.id !== selected()),
      soldiers: value.soldiers.filter((entry) => entry.id !== selected()),
    });
    setSelected("");
    setPlacing(null);
  }
  return (
    <section class="view-settings mission-settings">
      <h2>Mission</h2>
      <p class="hint">
        Add PC spawn points and NPC soldiers for this mission. Blue markers are PCs; red markers are
        NPCs. These placements are saved separately from map assets and included in the exported
        mod.
      </p>
      <fieldset disabled={!props.document()}>
        <div class="actions">
          <button onClick={() => setPlacing("pc")}>Add PC</button>
          <button onClick={() => setPlacing("npc")}>Add NPC</button>
        </div>
        <Show when={placing()}>
          <p role="status">
            Click the map to{" "}
            {placing() === "move"
              ? "move the selected marker"
              : placing() === "pc"
                ? "place a PC spawn"
                : "place a soldier"}
            . <button onClick={() => setPlacing(null)}>Cancel placement</button>
          </p>
        </Show>
        <label>
          Mission placement
          <select
            value={selected()}
            onChange={(event) => {
              setSelected(event.currentTarget.value);
              setPlacing(null);
            }}
          >
            <option value="">Choose a placement</option>
            <For each={entries()}>
              {(entry) => (
                <option value={entry.id}>
                  {entry.kind === "pc" ? "PC" : "NPC"} · {entry.name}
                </option>
              )}
            </For>
          </select>
        </label>
        <Show when={current()}>
          {(entry) => (
            <>
              <label>
                Name
                <input
                  value={entry().name}
                  onChange={(event) => change({ name: event.currentTarget.value })}
                />
              </label>
              <Show
                when={entry().kind === "pc"}
                fallback={
                  <>
                    <label>
                      Soldier profile
                      <input
                        value={entry().profile}
                        onChange={(event) => {
                          const value = mission();
                          publish({
                            ...value,
                            soldiers: value.soldiers.map((soldier) =>
                              soldier.id === selected()
                                ? { ...soldier, profile: event.currentTarget.value }
                                : soldier,
                            ),
                          });
                        }}
                      />
                    </label>
                    <p class="hint">
                      Use a soldier profile identifier from the game’s character library.
                    </p>
                    <label>
                      Allegiance
                      <input
                        type="number"
                        min="0"
                        max="65535"
                        step="1"
                        value={
                          mission().soldiers.find((soldier) => soldier.id === selected())
                            ?.allegiance ?? 1
                        }
                        onChange={(event) => {
                          const allegiance = event.currentTarget.valueAsNumber;
                          const value = mission();
                          publish({
                            ...value,
                            soldiers: value.soldiers.map((soldier) =>
                              soldier.id === selected() ? { ...soldier, allegiance } : soldier,
                            ),
                          });
                        }}
                      />
                    </label>
                  </>
                }
              >
                <label>
                  PC profile
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={entry().profile}
                    onChange={(event) => {
                      const profile = event.currentTarget.valueAsNumber;
                      const value = mission();
                      publish({
                        ...value,
                        spawnPoints: value.spawnPoints.map((spawn) =>
                          spawn.id === selected() ? { ...spawn, profile } : spawn,
                        ),
                      });
                    }}
                  />
                </label>
                <p class="hint">
                  Profile 0 is Robin. The chosen PC appears at this spawn when the mission starts.
                </p>
              </Show>
              <For each={["X", "Y", "Height"]}>
                {(label, index) => (
                  <label>
                    {label}
                    <input
                      type="number"
                      step="1"
                      value={entry().position[index()]}
                      onChange={(event) => {
                        const position: Vec3 = [...entry().position];
                        position[index()] = event.currentTarget.valueAsNumber;
                        change({ position });
                      }}
                    />
                  </label>
                )}
              </For>
              <label>
                Direction (0–15)
                <input
                  type="number"
                  min="0"
                  max="15"
                  step="1"
                  value={entry().direction}
                  onChange={(event) => change({ direction: event.currentTarget.valueAsNumber })}
                />
              </label>
              <div class="actions">
                <button onClick={() => setPlacing("move")}>Move on map</button>
                <button onClick={remove}>Delete placement</button>
              </div>
            </>
          )}
        </Show>
      </fieldset>
    </section>
  );
}
