import { For, Show, createEffect, createSignal, onCleanup, untrack } from "solid-js";
import { parseLevel3D, type Level3D, type Vec3 } from "@rle/shared";
import type { EditorViewport } from "./editor-viewport.ts";
import ScrubNumber from "./ScrubNumber";
import MissionCharacterChoices from "./MissionCharacterChoices";
import {
  loadMissionCharacterCatalog,
  type MissionCharacterProfile,
} from "./mission-character-catalog.ts";

export default function MissionPanel(props: {
  document(): Level3D | null;
  commit(document: Level3D): void;
  onError(message: string): void;
  active: boolean;
  viewport: EditorViewport;
  library?(): FileSystemDirectoryHandle | null;
}) {
  const [catalog, setCatalog] = createSignal<{
    root: FileSystemDirectoryHandle;
    profiles: MissionCharacterProfile[];
  } | null>(null);
  const [catalogStatus, setCatalogStatus] = createSignal("");
  const [spriteStatus, setSpriteStatus] = createSignal("");
  let catalogGeneration = 0;
  createEffect(
    () => ({ library: props.library?.() ?? null }),
    ({ library }) => {
      const generation = ++catalogGeneration;
      setCatalog(null);
      props.viewport.setMissionSpriteLibrary(null, [], () => {});
      setCatalogStatus(
        library
          ? "Loading library characters…"
          : "Open the asset library to choose character sprites.",
      );
      if (library)
        void loadMissionCharacterCatalog(library)
          .then((catalog) => {
            if (generation !== catalogGeneration) return;
            setCatalog(catalog);
            setCatalogStatus("");
            props.viewport.setMissionSpriteLibrary(
              catalog.root,
              catalog.profiles,
              (loading, warnings) => {
                if (generation === catalogGeneration)
                  setSpriteStatus(
                    loading ? "Loading placed character sprites…" : warnings.join("\n"),
                  );
              },
            );
          })
          .catch((error) => {
            if (generation === catalogGeneration) setCatalogStatus(String(error));
          });
    },
  );
  onCleanup(() => {
    catalogGeneration++;
    props.viewport.setMissionSpriteLibrary(null, [], () => {});
  });
  const [selected, setSelected] = createSignal("");
  const [placing, setPlacing] = createSignal<"pc" | "npc" | "move" | null>(null);
  const [pcProfile, setPcProfile] = createSignal(0);
  const [npcProfile, setNpcProfile] = createSignal("guard_a01");
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
  const paletteKind = () =>
    placing() === "pc" ? "pc" : placing() === "npc" ? "npc" : (current()?.kind ?? "pc");
  const paletteProfile = () =>
    placing() === "pc"
      ? pcProfile()
      : placing() === "npc"
        ? npcProfile()
        : (current()?.profile ?? pcProfile());
  function chooseCharacter(profile: MissionCharacterProfile) {
    if (profile.kind === "pc" && typeof profile.profile === "number") setPcProfile(profile.profile);
    if (profile.kind === "npc" && typeof profile.profile === "string")
      setNpcProfile(profile.profile);
    if (placing() === "pc" || placing() === "npc" || !current()) {
      setPlacing(profile.kind);
      return;
    }
    const value = mission();
    if (profile.kind === "pc" && typeof profile.profile === "number") {
      const id = profile.profile;
      publish({
        ...value,
        spawnPoints: value.spawnPoints.map((spawn) =>
          spawn.id === selected() ? { ...spawn, profile: id } : spawn,
        ),
      });
    } else if (profile.kind === "npc" && typeof profile.profile === "string") {
      const id = profile.profile;
      publish({
        ...value,
        soldiers: value.soldiers.map((soldier) =>
          soldier.id === selected() ? { ...soldier, profile: id } : soldier,
        ),
      });
    }
  }
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
  function cancelPreview() {
    const document = props.document();
    if (document) props.viewport.syncViews(document);
  }
  function preview(patch: { position?: Vec3; direction?: number }) {
    const document = props.document();
    if (!document) return;
    const value = mission();
    props.viewport.syncViews({
      ...document,
      mission: {
        ...value,
        spawnPoints: value.spawnPoints.map((entry) =>
          entry.id === selected() ? { ...entry, ...patch } : entry,
        ),
        soldiers: value.soldiers.map((entry) =>
          entry.id === selected() ? { ...entry, ...patch } : entry,
        ),
      },
    });
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
          ? { ...value, spawnPoints: [...value.spawnPoints, { ...base, profile: pcProfile() }] }
          : {
              ...value,
              soldiers: [...value.soldiers, { ...base, profile: npcProfile(), allegiance: 1 }],
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
        Add PC spawn points and NPC soldiers for this mission. Blue outlines are PCs; red outlines
        are NPCs. These placements are saved separately from map assets and included in the exported
        mod.
      </p>
      <Show when={catalogStatus()}>
        <p role="status">{catalogStatus()}</p>
      </Show>
      <Show when={spriteStatus()}>
        <p role="status">{spriteStatus()}</p>
      </Show>
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
        <Show when={catalog() && props.document()}>
          <MissionCharacterChoices
            root={catalog()!.root}
            camera={props.document()!.camera}
            profiles={catalog()!.profiles.filter((profile) => profile.kind === paletteKind())}
            selected={paletteProfile()}
            choose={chooseCharacter}
          />
        </Show>
        <Show when={placing() !== "pc" && placing() !== "npc" && current()}>
          {(entry) => (
            <>
              <label>
                Name
                <input
                  value={entry().name}
                  onChange={(event) => change({ name: event.currentTarget.value })}
                />
              </label>
              <Show when={entry().kind === "npc"}>
                <ScrubNumber
                  label="Allegiance"
                  value={
                    mission().soldiers.find((soldier) => soldier.id === selected())?.allegiance ?? 1
                  }
                  step={1}
                  min={0}
                  max={65535}
                  onPreview={() => {}}
                  onCancel={() => {}}
                  onCommit={(value) => {
                    const next = mission();
                    publish({
                      ...next,
                      soldiers: next.soldiers.map((soldier) =>
                        soldier.id === selected()
                          ? { ...soldier, allegiance: Math.round(value) }
                          : soldier,
                      ),
                    });
                  }}
                />
              </Show>
              <For each={["X", "Y", "Height"]}>
                {(label, index) => (
                  <ScrubNumber
                    label={label}
                    value={entry().position[index()]!}
                    step={1}
                    onPreview={(value) => {
                      const position: Vec3 = [...entry().position];
                      position[index()] = value;
                      preview({ position });
                    }}
                    onCancel={cancelPreview}
                    onCommit={(value) => {
                      cancelPreview();
                      const position: Vec3 = [...entry().position];
                      position[index()] = value;
                      change({ position });
                    }}
                  />
                )}
              </For>
              <ScrubNumber
                label="Direction (0–15)"
                value={entry().direction}
                step={1}
                min={0}
                max={15}
                onPreview={(value) => preview({ direction: Math.round(value) })}
                onCancel={cancelPreview}
                onCommit={(value) => {
                  cancelPreview();
                  change({ direction: Math.round(value) });
                }}
              />
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
