import { For, Show, createEffect, createSignal, onCleanup } from "solid-js";
import type { MapCamera } from "@rle/shared";
import { MissionEntities } from "./mission.ts";
import {
  DEFAULT_CHARACTER_DIRECTION,
  CHARACTER_DRAG_TYPE,
  type MissionCharacterProfile,
} from "./mission-character-catalog.ts";

function CharacterThumbnail(props: {
  root: FileSystemDirectoryHandle;
  camera: MapCamera;
  profile: MissionCharacterProfile;
  onReady(ready: boolean): void;
}) {
  const [url, setUrl] = createSignal("");
  const [error, setError] = createSignal("");
  let element!: HTMLDivElement;
  let generation = 0;
  let objectUrl = "";
  createEffect(
    () => ({ root: props.root, camera: props.camera, profile: props.profile }),
    ({ root, camera, profile }) => {
      const token = ++generation;
      setUrl("");
      setError("");
      props.onReady(false);
      let started = false;
      const observer = new IntersectionObserver(
        (entries) => {
          if (started || !entries.some((entry) => entry.isIntersecting)) return;
          started = true;
          observer.disconnect();
          void (async () => {
            let sprite: MissionEntities | undefined;
            try {
              sprite = await MissionEntities.loadCharacter(
                root,
                profile,
                camera,
                () => token === generation,
                [DEFAULT_CHARACTER_DIRECTION],
              );
              if (token !== generation) return;
              const blob = await sprite.thumbnail(DEFAULT_CHARACTER_DIRECTION);
              if (token !== generation) return;
              if (objectUrl) URL.revokeObjectURL(objectUrl);
              objectUrl = URL.createObjectURL(blob);
              setUrl(objectUrl);
              props.onReady(true);
            } catch (error) {
              if (token === generation) setError(String(error));
            } finally {
              sprite?.dispose();
            }
          })();
        },
        { rootMargin: "80px" },
      );
      observer.observe(element);
      onCleanup(() => {
        generation++;
        observer.disconnect();
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = "";
      });
    },
  );
  return (
    <div
      ref={(node) => {
        element = node;
      }}
      class="mission-character-thumb"
      style={{ height: "96px", display: "grid", "place-items": "center" }}
    >
      <Show
        when={url()}
        fallback={<span title={error()}>{error() ? "Sprite unavailable" : "Loading…"}</span>}
      >
        <img
          src={url()}
          alt={props.profile.name}
          style={{ "max-height": "96px", "max-width": "100%", "image-rendering": "pixelated" }}
        />
      </Show>
    </div>
  );
}

function CharacterChoice(props: {
  root: FileSystemDirectoryHandle;
  camera: MapCamera;
  profile: MissionCharacterProfile;
}) {
  const [ready, setReady] = createSignal(false);
  return (
    <article
      class="asset-card"
      draggable={ready() ? "true" : "false"}
      aria-disabled={ready() ? "false" : "true"}
      data-character-profile={props.profile.profile}
      onDragStart={(event) => {
        if (!ready() || !event.dataTransfer) {
          event.preventDefault();
          return;
        }
        event.dataTransfer.setData(
          CHARACTER_DRAG_TYPE,
          `${props.profile.kind}:${props.profile.profile}`,
        );
        event.dataTransfer.effectAllowed = "copy";
      }}
    >
      <CharacterThumbnail
        root={props.root}
        camera={props.camera}
        profile={props.profile}
        onReady={setReady}
      />
      <div class="asset-card-info">
        <strong>{props.profile.name}</strong>
        <small>{props.profile.filename}</small>
      </div>
    </article>
  );
}

export default function MissionCharacterChoices(props: {
  root: FileSystemDirectoryHandle;
  camera: MapCamera;
  profiles: MissionCharacterProfile[];
}) {
  const [search, setSearch] = createSignal("");
  const filtered = () =>
    props.profiles.filter((profile) =>
      `${profile.name} ${profile.filename}`.toLowerCase().includes(search().toLowerCase()),
    );
  return (
    <div class="mission-character-choices">
      <label>
        Find character
        <input
          type="search"
          value={search()}
          onInput={(event) => setSearch(event.currentTarget.value)}
        />
      </label>
      <div
        class="asset-grid"
        role="group"
        aria-label="Character profiles"
        style={{ "max-height": "360px", overflow: "auto" }}
      >
        <For each={filtered()}>
          {(profile) => (
            <CharacterChoice root={props.root} camera={props.camera} profile={profile} />
          )}
        </For>
      </div>
      <Show when={!filtered().length}>
        <p class="hint">No matching characters.</p>
      </Show>
    </div>
  );
}
