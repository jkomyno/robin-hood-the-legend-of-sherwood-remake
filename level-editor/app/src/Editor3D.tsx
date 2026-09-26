// Edit JSON maps assembled from pinned library assets, with game and orbit cameras.
import { For, Show, createEffect, createMemo, createSignal, onCleanup } from "solid-js";
import type { JSX } from "@solidjs/web";
import type * as THREE from "three";
import {
  IDENTITY_TRANSFORM,
  serializeStoredMap,
  parseLevel3D,
  groupParts,
  isIdentity,
  type GameTransform,
  type Level3D,
  type Level3DGroup,
  type Level3DObject,
  type ProtoLevel,
  type ProjectionAssetEntry,
} from "@rle/shared";
import { SessionPublication, type SessionSnapshot } from "./session-publication";
import {
  duplicateSelection,
  setGroupState,
  stateOwner,
  deleteSelection,
  patchPart,
  patchGroup,
  type Selection,
} from "./document-commands";
import { createNewMap } from "./new-map";
import SplinePanel from "./SplinePanel";
import LightingPanel from "./LightingPanel";
import AssetLibrary from "./AssetLibrary";
import ScrubNumber from "./ScrubNumber";
import { ASSET_DRAG_TYPE } from "./asset-library";
import { insertProjectionAsset } from "./asset-commands";
import {
  listProjectionAssets,
  prepareProjectionAsset,
  readPinnedAssetDescriptors,
} from "./projection-library";
import { prepareMapCandidate } from "./map-candidate";
import { EditorViewport } from "./editor-viewport";
import { disposeObjectResources } from "./resources";
import { listFiles, subdir, writeText } from "./fs";
import { MissionEntities, readMission } from "./mission";
import { PopulationView, type SceneEntities } from "./population-view";
import type { DatadirIndex } from "./datadir";
import { missionsForMap } from "./mission-catalog.ts";
import { downloadMap } from "./http-library.ts";

export type { Selection } from "./document-commands";

/** the library directory handle, wrapped because handles are async-iterable and Solid 2 would iterate them */
export interface LibraryRef {
  handle: FileSystemDirectoryHandle;
  mapLabels?: () => Promise<ReadonlyMap<string, string>>;
  documentMap?: (name: string) => string;
  savedMapName?: (name: string) => string;
}

export interface EditorProps {
  index: () => DatadirIndex | null;
  library: () => LibraryRef | null;
  onError: (msg: string) => void;
  onStatus: (msg: string | null) => void;
  toolbarStart?: () => JSX.Element;
  toolbarEnd?: () => JSX.Element;
}

export default function Editor3D(props: EditorProps) {
  let viewportElement!: HTMLDivElement;
  let newMapDialog!: HTMLDialogElement;
  const [newMapName, setNewMapName] = createSignal("Untitled map");
  const [creatingMap, setCreatingMap] = createSignal(false);
  const [newMapError, setNewMapError] = createSignal("");
  const [panel, setPanel] = createSignal("Selection");
  const [libraryOpen, setLibraryOpen] = createSignal(true);
  const [libraryWidth, setLibraryWidth] = createSignal(284);
  let libraryResize: { x: number; width: number } | undefined;
  const maxLibraryWidth = () => Math.max(200, Math.min(600, window.innerWidth * 0.45));
  const resizeLibrary = (width: number) =>
    setLibraryWidth(Math.max(200, Math.min(maxLibraryWidth(), width)));
  const [helpOpen, setHelpOpen] = createSignal(false);
  const [editingPath, setEditingPath] = createSignal(false);
  const [missionName, setMissionName] = createSignal("");
  const [missionInfo, setMissionInfo] = createSignal("");
  const [populationPlaying, setPopulationPlaying] = createSignal(true);
  const [populationRoutes, setPopulationRoutes] = createSignal(false);
  const [perspective, setPerspective] = createSignal(0);
  const [rotationSnap, setRotationSnap] = createSignal(false);
  const [spriteOrientationLock, setSpriteOrientationLock] = createSignal(true);
  const [showEntities, setShowEntities] = createSignal(true);
  const [smoothTextures, setSmoothTextures] = createSignal(
    localStorage.getItem("rle.smoothTextures") !== "false",
  );
  const [synthesizedTextures, setSynthesizedTextures] = createSignal(
    localStorage.getItem("rle.synthesizedTextures") !== "false",
  );
  const [patchPreviewRevision, setPatchPreviewRevision] = createSignal(0);
  let openAttempt = 0;
  let loadedIndex: DatadirIndex | null = null;
  let loadedLibrary: LibraryRef | null = null;
  let transientMapName: string | null = null;
  const [maps, setMaps] = createSignal<string[]>([]);
  const [mapLabels, setMapLabels] = createSignal<ReadonlyMap<string, string>>(new Map());
  const mapLabel = (name: string) => mapLabels().get(name) ?? name;
  const [assetEntries, setAssetEntries] = createSignal<ProjectionAssetEntry[]>([]);
  const [libraryLoading, setLibraryLoading] = createSignal(false);
  const [libraryError, setLibraryError] = createSignal("");
  const [mapLoadProgress, setMapLoadProgress] = createSignal<{
    completed: number;
    total: number;
    phase: string;
  } | null>(null);
  const [dropActive, setDropActive] = createSignal(false);
  const [addingAsset, setAddingAsset] = createSignal(false);
  let paletteAttempt = 0;
  const [revision, setRevision] = createSignal<SessionSnapshot<Level3D> | null>(null);
  const mapName = createMemo(() => revision()?.name ?? null);
  const doc = createMemo(() => revision()?.document ?? null);
  const dirty = createMemo(() => revision()?.dirty ?? false);
  const history = createMemo(() => revision() ?? { past: [], future: [] });
  const canInsert = createMemo(() => !!doc() && !addingAsset());
  const session = new SessionPublication<Level3D, FileSystemDirectoryHandle>((snapshot, reason) => {
    setRevision(snapshot);
    if (reason === "revision") viewport.syncViews(snapshot.document, false);
  });
  let saving = false;
  let disposed = false;
  const [selected, setSelected] = createSignal<Selection>(null);
  const [filter, setFilter] = createSignal("");
  const [expanded, setExpanded] = createSignal<Set<string>>(new Set());
  const [showObstacles, setShowObstacles] = createSignal(false);
  const [showElevation, setShowElevation] = createSignal(false);
  const [gizmoVertical, setGizmoVertical] = createSignal(false);
  const [level, setLevel] = createSignal<ProtoLevel | null>(null);
  /** obstacle index -> suggested snap (Δ along the view ray, support obstacle) */
  const [suspects, setSuspects] = createSignal<Map<number, { delta: number; support: number }>>(
    new Map(),
  );
  const [info, setInfo] = createSignal<string | null>(null);
  const viewport = new EditorViewport({
    document: doc,
    selection: selected,
    level,
    showObstacles,
    showElevation,
    onSelection: (selection) => {
      setSelected(selection);
      if (selection?.kind === "part") {
        const group = doc()?.objects.find((o) => o.id === selection.id)?.group;
        if (group) setExpanded((current) => new Set(current).add(group));
      }
    },
    commitTransform: setTransform,
  });
  const select = (selection: Selection) => viewport.select(selection);

  // ── scenes in the library ──
  createEffect(
    () => props.library(),
    (lib) => {
      session.beginLoad();
      openAttempt++;
      setMaps([]);
      transientMapName = null;
      setMapLabels(new Map());
      if (!lib) return;
      void (async () => {
        const dir = await subdir(lib.handle, ["scenes"]);
        if (!dir) return;
        const files = await listFiles(dir);
        const labels = (await lib.mapLabels?.()) ?? new Map<string, string>();
        const names = files
          .filter((f) => f.endsWith(".rhlos-map.json"))
          .map((f) => f.slice(0, -".rhlos-map.json".length))
          .sort();
        if (disposed || props.library() !== lib) return;
        setMaps(names);
        setMapLabels(labels);
        if (names.length === 1) void openMap(names[0]!);
      })().catch((error) => {
        if (!disposed && props.library() === lib) props.onError(String(error));
      });
    },
  );

  createEffect(
    () => props.library(),
    (library) => {
      const attempt = ++paletteAttempt;
      setAssetEntries([]);
      setLibraryError("");
      setLibraryLoading(!!library);
      if (!library) return;
      void listProjectionAssets(library.handle)
        .then((entries) => {
          if (!disposed && attempt === paletteAttempt && props.library() === library)
            setAssetEntries(entries);
        })
        .catch((error) => {
          if (!disposed && attempt === paletteAttempt) setLibraryError(String(error));
        })
        .finally(() => {
          if (!disposed && attempt === paletteAttempt) setLibraryLoading(false);
        });
    },
  );

  function viewportElementCenter() {
    const bounds = viewportElement.getBoundingClientRect();
    return { x: bounds.left + bounds.width / 2, y: bounds.top + bounds.height / 2 };
  }

  type PreparedAsset = Awaited<ReturnType<typeof prepareProjectionAsset>>;
  type WarmAsset = {
    id: string;
    library: LibraryRef;
    map: string;
    retired: boolean;
    value: PreparedAsset | null;
    promise: Promise<PreparedAsset>;
  };
  let warmAsset: WarmAsset | null = null;
  function clearWarmAsset() {
    const old = warmAsset;
    warmAsset = null;
    if (old) {
      old.retired = true;
      if (old.value) disposeObjectResources([old.value.asset]);
      old.value = null;
    }
  }
  function preloadAsset(entry: ProjectionAssetEntry) {
    const document = doc(),
      library = props.library();
    if (!document || !library) return null;
    if (
      warmAsset?.id === entry.id &&
      warmAsset.library === library &&
      warmAsset.map === document.map
    )
      return warmAsset;
    clearWarmAsset();
    const next: WarmAsset = {
      id: entry.id,
      library,
      map: document.map,
      retired: false,
      value: null,
      promise: prepareProjectionAsset(library.handle, entry, document.map).then((value) => {
        if (next.retired) {
          disposeObjectResources([value.asset]);
          throw new Error("Asset preload cancelled");
        }
        next.value = value;
        return value;
      }),
    };
    // Hover failures are reported if the user actually attempts placement.
    void next.promise.catch(() => {});
    return (warmAsset = next);
  }
  async function takeAsset(entry: ProjectionAssetEntry) {
    const pending = preloadAsset(entry);
    if (!pending) throw new Error("Open a map before placing assets");
    const result = await pending.promise;
    pending.value = null;
    if (warmAsset === pending) warmAsset = null;
    return result;
  }
  type AssetDrag = {
    entry: ProjectionAssetEntry;
    base: Level3D;
    attempt: number;
    inside: boolean;
    dropped: boolean;
    position: [number, number, number] | null;
    result: ReturnType<typeof insertProjectionAsset> | null;
  };
  let assetDrag: AssetDrag | null = null;
  function hideAssetDrag() {
    if (assetDrag) {
      assetDrag.inside = false;
      if (assetDrag.result && doc()) viewport.syncViews(doc()!, false);
    }
    setDropActive(false);
  }
  function cancelAssetDrag() {
    hideAssetDrag();
    assetDrag = null;
    clearWarmAsset();
  }
  function updateAssetDrag() {
    const drag = assetDrag;
    if (!drag || !drag.result || !drag.position || !drag.inside) return;
    if (doc() !== drag.base || openAttempt !== drag.attempt) {
      cancelAssetDrag();
      return;
    }
    const group = drag.result.document.groups.find(
      (group) => group.id === drag.result!.selection.id,
    )!;
    [group.transform.dx, group.transform.dy, group.transform.dz] = drag.position;
    viewport.syncViews(drag.result.document, false);
    if (drag.dropped) {
      assetDrag = null;
      pushHistory(drag.result.document);
      select(drag.result.selection);
      setInfo(`Added ${drag.entry.name}`);
      setDropActive(false);
    }
  }
  async function startAssetDrag(entry: ProjectionAssetEntry) {
    if (!doc() || addingAsset()) return;
    if (assetDrag) cancelAssetDrag();
    const drag: AssetDrag = {
      entry,
      base: doc()!,
      attempt: openAttempt,
      inside: false,
      dropped: false,
      position: null,
      result: null,
    };
    assetDrag = drag;
    let prepared: PreparedAsset | null = null;
    try {
      prepared = await takeAsset(entry);
      if (disposed || assetDrag !== drag || doc() !== drag.base || openAttempt !== drag.attempt)
        return;
      drag.result = insertProjectionAsset(
        drag.base,
        prepared.descriptor,
        prepared.reference,
        [0, 0, 0],
      );
      parseLevel3D(drag.result.document, { level: level() ?? undefined });
      if (!viewport.adoptAsset(prepared.reference, prepared.asset, prepared.sources))
        disposeObjectResources([prepared.asset]);
      prepared = null;
      updateAssetDrag();
    } catch (error) {
      if (!disposed && assetDrag === drag) {
        cancelAssetDrag();
        props.onError(String(error));
      }
    } finally {
      if (prepared) disposeObjectResources([prepared.asset]);
    }
  }

  async function addAsset(entry: ProjectionAssetEntry, placement?: [number, number, number]) {
    const document = doc();
    const library = props.library();
    const attempt = openAttempt;
    if (!document || !library || addingAsset()) return;
    setAddingAsset(true);
    let prepared: Awaited<ReturnType<typeof prepareProjectionAsset>> | null = null;
    try {
      prepared = await takeAsset(entry);
      if (disposed || attempt !== openAttempt || props.library() !== library || doc() !== document)
        return;
      const center = viewportElementCenter();
      const position = placement ?? viewport.assetDropPosition(center.x, center.y);
      if (!position) throw new Error("Point the camera toward the ground before adding an asset.");
      const result = insertProjectionAsset(
        document,
        prepared.descriptor,
        prepared.reference,
        position,
      );
      parseLevel3D(result.document, { level: level() ?? undefined });
      const adopted = viewport.adoptAsset(prepared.reference, prepared.asset, prepared.sources);
      if (!adopted) disposeObjectResources([prepared.asset]);
      prepared = null;
      pushHistory(result.document);
      select(result.selection);
      setInfo(`Added ${entry.name}`);
    } catch (error) {
      if (!disposed && attempt === openAttempt) props.onError(String(error));
    } finally {
      if (prepared) disposeObjectResources([prepared.asset]);
      if (!disposed) setAddingAsset(false);
    }
  }

  async function createMap(name: string) {
    const library = props.library();
    if (!library || creatingMap()) return;
    setCreatingMap(true);
    setNewMapError("");
    try {
      if (dirty()) {
        await save();
        if (dirty())
          throw new Error("Save the current map successfully before creating another map.");
      }
      if (disposed || props.library() !== library) return;
      name = await createNewMap(library.handle, name);
      if (disposed || props.library() !== library) return;
      setMaps((current) => [...new Set([...current, name])].sort());
      newMapDialog.close();
      setPanel("Selection");
      await openMap(name);
    } catch (error) {
      if (!disposed) setNewMapError(error instanceof Error ? error.message : String(error));
    } finally {
      if (!disposed) setCreatingMap(false);
    }
  }

  // ── document ──
  function pushHistory(next: Level3D) {
    session.edit(next);
  }
  function undo() {
    session.undo();
  }
  function redo() {
    session.redo();
  }
  function updatePart(id: string, patch: Partial<Level3DObject>) {
    const d = doc();
    if (!d) return;
    pushHistory(patchPart(d, id, patch));
  }
  function updateGroup(id: string, patch: Partial<Level3DGroup>) {
    const d = doc();
    if (!d) return;
    pushHistory(patchGroup(d, id, patch));
  }
  const selectedPart = () => {
    const s = selected();
    return s?.kind === "part" ? (doc()?.objects.find((o) => o.id === s.id) ?? null) : null;
  };
  const selectedGroup = () => {
    const s = selected();
    return s?.kind === "group" ? (doc()?.groups.find((g) => g.id === s.id) ?? null) : null;
  };
  /** the transform the panel edits: the selected group's or part's */
  const selectedTransform = (): GameTransform | null =>
    selectedGroup()?.transform ?? selectedPart()?.transform ?? null;
  function setTransform(t: GameTransform) {
    const g = selectedGroup();
    const p = selectedPart();
    if (g) updateGroup(g.id, { transform: t });
    else if (p) updatePart(p.id, { transform: t });
  }

  async function openMap(name: string, requestedMission?: string, importedFile?: File) {
    cancelAssetDrag();
    const lib = props.library();
    const idx = props.index();
    if (!lib) return;
    const attempt = ++openAttempt;
    const generation = session.beginLoad();
    const current = () =>
      !disposed && attempt === openAttempt && props.index() === idx && props.library() === lib;
    let preparedAsset: THREE.Object3D | null = null;
    let preparedEntities: SceneEntities | null = null;
    props.onStatus(`loading ${requestedMission ?? mapLabel(name)}…`);
    setMapLoadProgress({ completed: 0, total: 1, phase: "Reading map" });
    try {
      let importedDocument: unknown;
      if (importedFile) {
        importedDocument = JSON.parse(await importedFile.text());
        const id = (importedDocument as { map?: unknown }).map;
        if (typeof id !== "string" || !id || id === "." || id === ".." || /[\\/\0]/.test(id))
          throw new Error("Invalid map name in dropped JSON");
        name = lib.savedMapName?.(id) ?? id;
      }
      const mission = requestedMission && idx ? await readMission(idx, requestedMission) : null;
      if (mission) {
        const matching =
          (doc()?.sourceMap ?? doc()?.map)?.toLowerCase() === mission.map.toLowerCase()
            ? mapName()
            : maps().find((m) => m.toLowerCase() === mission.map.toLowerCase());
        if (!matching) throw new Error(`No published map for ${mission.map} in this library`);
        name = matching;
      }
      if (disposed || attempt !== openAttempt) return;
      const currentDocument = doc();
      const currentLevel = level();
      if (
        !importedFile &&
        name === mapName() &&
        currentDocument &&
        loadedIndex === idx &&
        loadedLibrary === lib
      ) {
        if (mission && idx && currentLevel)
          preparedEntities = await MissionEntities.load(
            idx,
            mission,
            currentLevel,
            currentDocument.camera,
            current,
          );
        else if (currentDocument.population)
          preparedEntities = await PopulationView.load(
            lib.handle,
            currentDocument.population,
            currentDocument.camera,
            current,
          );
        if (
          disposed ||
          attempt !== openAttempt ||
          props.index() !== idx ||
          props.library() !== lib
        ) {
          preparedEntities?.dispose();
          return;
        }
        viewport.replaceEntities(preparedEntities);
        viewport.setEntitiesVisible(showEntities());
        viewport.setPopulationPlaying(populationPlaying());
        viewport.setPopulationRoutesVisible(populationRoutes());
        setMissionName(mission?.name ?? "");
        setMissionInfo(
          preparedEntities
            ? `${preparedEntities.count} entities. ${preparedEntities.warnings.join("; ")}`
            : "",
        );
        preparedEntities = null;
        props.onStatus(null);
        setMapLoadProgress(null);
        return;
      }
      const candidate = await prepareMapCandidate(
        name,
        lib.handle,
        idx,
        (completed, total, phase) => {
          if (attempt === openAttempt) setMapLoadProgress({ completed, total, phase });
        },
        lib.documentMap?.(name) ?? name,
        importedDocument,
      );
      preparedAsset = candidate.asset;
      if (mission && idx) {
        if (!candidate.level) throw new Error("Mission requires level data");
        preparedEntities = await MissionEntities.load(
          idx,
          mission,
          candidate.level,
          candidate.document.camera,
          current,
        );
      } else if (candidate.document.population) {
        preparedEntities = await PopulationView.load(
          lib.handle,
          candidate.document.population,
          candidate.document.camera,
          current,
        );
      }
      const {
        document: d,
        directory: dir,
        level: lvl,
        sources: nextSources,
        ground: nextGround,
        suspects: nextSuspects,
      } = candidate;
      if (
        disposed ||
        !session.isCurrent(generation) ||
        attempt !== openAttempt ||
        props.library() !== lib ||
        props.index() !== idx
      ) {
        preparedEntities?.dispose();
        preparedEntities = null;
        disposeObjectResources([preparedAsset]);
        preparedAsset = null;
        return;
      }
      // All asynchronous reads and validation precede publication.
      viewport.replaceMap(preparedAsset, nextGround, nextSources, d.assetSources);
      preparedAsset = null;
      viewport.replaceEntities(preparedEntities);
      viewport.setEntitiesVisible(showEntities());
      viewport.setPopulationPlaying(populationPlaying());
      viewport.setPopulationRoutesVisible(populationRoutes());
      setMissionName(mission?.name ?? "");
      setMissionInfo(
        preparedEntities
          ? `${preparedEntities.count} entities. ${preparedEntities.warnings.join("; ")}`
          : "",
      );
      preparedEntities = null;
      if (transientMapName && transientMapName !== name) {
        const previous = transientMapName;
        setMaps((names) => names.filter((name) => name !== previous));
        transientMapName = null;
      }
      if (importedFile) {
        if (!maps().includes(name)) transientMapName = name;
        setMaps((names) => [...new Set([...names, name])].sort());
        const sourceName = lib.documentMap?.(name) ?? name;
        if (sourceName !== name)
          setMapLabels((labels) =>
            new Map(labels).set(name, `${labels.get(sourceName) ?? sourceName} (Modified)`),
          );
      }
      session.publish(generation, name, d, dir, candidate.saved && !importedFile);
      loadedIndex = idx;
      loadedLibrary = lib;
      setLevel(lvl);
      setSuspects(nextSuspects);
      viewport.syncViews(d);
      viewport.buildOverlays();
      viewport.gameCamera(true);
      setInfo(`${d.groups.length} buildings, ${d.objects.length} parts`);
      props.onStatus(null);
      setMapLoadProgress(null);
    } catch (e) {
      preparedEntities?.dispose();
      if (preparedAsset) disposeObjectResources([preparedAsset]);
      if (session.isCurrent(generation) && !disposed) {
        props.onStatus(null);
        setMapLoadProgress(null);
        props.onError(String(e));
      }
    }
  }

  createEffect(
    () => props.index(),
    () => {
      openAttempt++;
      session.beginLoad();
      viewport.replaceEntities(null);
      setMissionName("");
      setMissionInfo("");
    },
  );
  createEffect(
    () => perspective(),
    (value) => viewport.setPerspective(value),
  );
  createEffect(
    () => rotationSnap(),
    (value) => viewport.setRotationSnap(value),
  );
  createEffect(
    () => spriteOrientationLock(),
    (value) => viewport.setSpriteOrientationLock(value),
  );
  createEffect(
    () => showEntities(),
    (value) => viewport.setEntitiesVisible(value),
  );
  createEffect(
    () => ({ smooth: smoothTextures(), synthesized: synthesizedTextures() }),
    (value) => {
      viewport.setTextureDisplay(value.smooth, value.synthesized);
      localStorage.setItem("rle.smoothTextures", String(value.smooth));
      localStorage.setItem("rle.synthesizedTextures", String(value.synthesized));
    },
  );

  createEffect(
    () => ({ obstacles: showObstacles(), elevation: showElevation() }),
    () => viewport.buildOverlays(),
  );
  createEffect(
    () => gizmoVertical(),
    (v) => viewport.setGizmoVertical(v),
  );

  // ── actions ──
  const selectedStatePart = () => {
    const d = doc();
    const p = selectedPart();
    return d && p ? stateOwner(d, p.id) : undefined;
  };
  function duplicateSelected() {
    const document = doc();
    const selection = selected();
    if (!document || !selection || selectedStatePart()) return;
    const result = duplicateSelection(document, selection);
    pushHistory(result.document);
    select(result.selection);
  }
  function deleteSelected() {
    const document = doc();
    const selection = selected();
    if (!document || !selection || selectedStatePart()) return;
    const next = deleteSelection(document, selection);
    select(null);
    pushHistory(next);
  }
  function rotateSelected(delta: number) {
    const t = selectedTransform();
    if (!t) return;
    setTransform({ ...t, rot_deg: (((t.rot_deg + delta) % 360) + 360) % 360 });
  }
  function setTransformField(field: keyof GameTransform, value: number) {
    const t = selectedTransform();
    if (!t || !Number.isFinite(value)) return;
    setTransform({ ...t, [field]: value });
  }
  function previewTransformField(field: keyof GameTransform, value: number) {
    const document = doc(),
      transform = selectedTransform(),
      selection = selected();
    if (!document || !transform || !selection) return;
    const changes = { transform: { ...transform, [field]: value } };
    const next =
      selection.kind === "group"
        ? patchGroup(document, selection.id, changes)
        : patchPart(document, selection.id, changes);
    viewport.syncViews(next, false);
  }
  function setHidden(hidden: boolean) {
    const g = selectedGroup();
    const p = selectedPart();
    if (g) updateGroup(g.id, { hidden });
    else if (p && !selectedStatePart()) updatePart(p.id, { hidden });
  }
  async function save() {
    if (!session.current || saving) return;
    const snapshot = session.captureSave();
    const library = props.library();
    saving = true;
    try {
      const descriptors = snapshot.document.assetSources?.length
        ? await readPinnedAssetDescriptors(library!.handle, snapshot.document.assetSources)
        : new Map();
      await writeText(
        snapshot.resources,
        `${snapshot.name}.rhlos-map.json`,
        JSON.stringify(serializeStoredMap(snapshot.document, descriptors), null, 2),
      );
      const savedName = library?.savedMapName?.(snapshot.name) ?? snapshot.name;
      if (transientMapName === snapshot.name) transientMapName = null;
      const labels = await library?.mapLabels?.();
      if (!disposed && props.library() === library) {
        if (labels) setMapLabels(labels);
        setMaps((names) => [...new Set([...names, savedName])].sort());
      }
      session.saved(snapshot, savedName);
      if (!disposed && session.current === snapshot.session) {
        props.onStatus(`Saved ${mapLabel(savedName)} in this browser`);
      }
    } catch (e) {
      if (!disposed) props.onError(String(e));
    } finally {
      saving = false;
    }
  }

  async function download() {
    const document = doc();
    if (!document) return;
    try {
      const descriptors = document.assetSources?.length
        ? await readPinnedAssetDescriptors(props.library()!.handle, document.assetSources)
        : new Map();
      downloadMap(document.map, serializeStoredMap(document, descriptors));
    } catch (error) {
      props.onError(String(error));
    }
  }

  function onKey(e: KeyboardEvent) {
    if (["INPUT", "SELECT", "TEXTAREA"].includes((e.target as HTMLElement).tagName)) return;
    if (e.key === "z" && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
      e.preventDefault();
      undo();
    } else if (
      (e.key === "z" && (e.ctrlKey || e.metaKey) && e.shiftKey) ||
      (e.key === "y" && e.ctrlKey)
    ) {
      e.preventDefault();
      redo();
    } else if (e.key === "s" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      void save();
    } else if (e.key === "Delete" || e.key === "Backspace") deleteSelected();
    else if (e.key === "d" && !e.ctrlKey) duplicateSelected();
    else if (e.key === "q") rotateSelected(-15);
    else if (e.key === "e") rotateSelected(15);
    else if (e.key === "g") viewport.gameCamera();
    else if (e.key === "f") viewport.frameContent();
    else if (e.key === "Escape") select(null);
  }
  window.addEventListener("keydown", onKey, {
    signal: viewport.listeners.signal,
  });
  onCleanup(() => {
    cancelAssetDrag();
    disposed = true;
    session.dispose();
    viewport.dispose();
  });

  // ── object list: buildings (expandable), then ungrouped parts and terraces ──
  interface Row {
    kind: "group" | "part";
    id: string;
    label: string;
    depth: number;
    hidden: boolean;
    moved: boolean;
    parts?: number;
    suspect?: boolean;
  }
  const rows = (): Row[] => {
    const d = doc();
    if (!d) return [];
    const q = filter().toLowerCase();
    const match = (id: string, name?: string) =>
      !q || id.toLowerCase().includes(q) || (name ?? "").toLowerCase().includes(q);
    const out: Row[] = [];
    const exp = expanded();
    for (const g of d.groups) {
      const parts = groupParts(d, g.id);
      const partMatch = parts.filter((p) => match(p.id, p.name));
      if (!match(g.id, g.name) && partMatch.length === 0) continue;
      out.push({
        kind: "group",
        id: g.id,
        label: g.name ?? g.id,
        depth: 0,
        hidden: !!g.hidden,
        moved: !isIdentity(g.transform),
        parts: parts.length,
        suspect: parts.some(
          (p) => p.source.obstacle !== undefined && suspects().has(p.source.obstacle),
        ),
      });
      if (exp.has(g.id) || (q && partMatch.length > 0)) {
        for (const p of parts)
          if (!q || match(p.id, p.name))
            out.push({
              kind: "part",
              id: p.id,
              label: p.name ?? p.id,
              depth: 1,
              hidden: !!p.hidden,
              moved: !isIdentity(p.transform),
              suspect: p.source.obstacle !== undefined && suspects().has(p.source.obstacle),
            });
      }
    }
    for (const o of d.objects) {
      if (o.group || !match(o.id, o.name)) continue;
      out.push({
        kind: "part",
        id: o.id,
        label: o.name ?? o.id,
        depth: 0,
        hidden: !!o.hidden,
        moved: !isIdentity(o.transform),
        suspect: o.source.obstacle !== undefined && suspects().has(o.source.obstacle),
      });
    }
    return out;
  };
  const isSelected = (r: Row) => {
    const s = selected();
    return !!s && s.kind === r.kind && s.id === r.id;
  };
  const toggleExpanded = (id: string) =>
    setExpanded((x) => {
      const n = new Set(x);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const selectionTitle = () => {
    const g = selectedGroup();
    const p = selectedPart();
    const d = doc();
    if (g && d) return `${g.name ?? g.id} (${groupParts(d, g.id).length} parts)`;
    if (p) return p.name ?? p.id;
    return "";
  };

  return (
    <div class="editor">
      <dialog
        class="new-map-dialog"
        ref={(element) => {
          newMapDialog = element;
        }}
        aria-labelledby="new-map-title"
        onCancel={(event) => {
          if (creatingMap()) event.preventDefault();
        }}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void createMap(String(new FormData(event.currentTarget).get("mapName")));
          }}
        >
          <h2 id="new-map-title">New map</h2>
          <p>Start with an open canvas. Add assets, walls and paths in any direction.</p>
          <fieldset disabled={creatingMap()}>
            <label>
              Map name
              <input
                name="mapName"
                aria-label="Map name"
                autofocus
                required
                maxlength={64}
                value={newMapName()}
                onInput={(event) => setNewMapName(event.currentTarget.value)}
              />
            </label>
            <p class="hint">
              No size to choose now. Set an optional export frame later, when you know what to
              include.
            </p>
            <p class="hint">Saved in this browser. Use Download to export the map JSON.</p>
            <Show when={dirty()}>
              <p class="hint">Your current map will be saved before creating the new one.</p>
            </Show>
            <Show when={newMapError()}>
              <p class="library-error" role="alert">
                {newMapError()}
              </p>
            </Show>
            <div class="dialog-actions">
              <button type="button" onClick={() => newMapDialog.close()}>
                Cancel
              </button>
              <button type="submit" class="primary-action">
                {creatingMap() ? "Creating…" : "Create map"}
              </button>
            </div>
          </fieldset>
        </form>
      </dialog>
      <header class="topbar editor-bar">
        {props.toolbarStart?.()}
        <button
          disabled={!props.library() || editingPath()}
          title={!props.library() ? "Waiting for assets" : "Create a blank map"}
          onClick={() => {
            setNewMapError("");
            newMapDialog.showModal();
          }}
        >
          New map
        </button>
        <label class="mission-picker">
          Map
          <select
            aria-label="Map"
            value={mapName() ?? ""}
            disabled={!maps().length}
            onChange={(event) => {
              const name = event.currentTarget.value;
              event.currentTarget.value = mapName() ?? "";
              if (name) void openMap(name);
            }}
          >
            <option value="" disabled>
              Choose a map…
            </option>
            <For each={maps()}>{(name) => <option value={name}>{mapLabel(name)}</option>}</For>
          </select>
        </label>
        <label class="mission-picker">
          Mission
          <select
            aria-label="Mission"
            value={missionName()}
            disabled={
              !props.index() ||
              !mapName() ||
              !missionsForMap(props.index(), doc()?.sourceMap ?? doc()?.map ?? mapName()).length
            }
            onChange={(e) => {
              const value = e.currentTarget.value;
              e.currentTarget.value = missionName();
              if (value) void openMap("", value);
              else if (mapName()) void openMap(mapName()!);
            }}
          >
            <option value="">Map only</option>
            <For each={missionsForMap(props.index(), doc()?.sourceMap ?? doc()?.map ?? mapName())}>
              {(mission) => <option value={mission.id}>{mission.label}</option>}
            </For>
          </select>
        </label>
        <span class="spacer" />
        <button disabled={!doc()} onClick={() => viewport.gameCamera()} title="g">
          Reset view
        </button>
        <button disabled={history().past.length === 0} onClick={undo} title="ctrl+z">
          Undo
        </button>
        <button disabled={history().future.length === 0} onClick={redo} title="ctrl+shift+z">
          Redo
        </button>
        <button
          class="primary-action"
          disabled={!dirty()}
          onClick={() => void save()}
          title="ctrl+s"
        >
          Save{dirty() ? " *" : ""}
        </button>
        <button disabled={!doc()} onClick={() => void download()}>
          Download
        </button>
        <button
          aria-expanded={helpOpen() ? "true" : "false"}
          aria-controls="editor-help"
          onClick={() => setHelpOpen(!helpOpen())}
        >
          Help
        </button>
        {props.toolbarEnd?.()}
      </header>
      <Show when={mapLoadProgress()}>
        {(progress) => (
          <div
            class="map-load-progress"
            role="status"
            aria-label={`Loading map: ${progress().phase}`}
          >
            <div class="map-load-progress-label">
              <span>{progress().phase}</span>
              <span>
                {progress().total > 1 ? `${progress().completed} / ${progress().total} assets` : ""}
              </span>
            </div>
            <progress max={progress().total} value={progress().completed} />
          </div>
        )}
      </Show>
      <div class="editor-body">
        <div
          id="asset-browser"
          class={`asset-browser${libraryOpen() ? "" : " collapsed"}`}
          style={{ width: libraryOpen() ? `${libraryWidth()}px` : "44px" }}
        >
          <AssetLibrary
            root={props.library()?.handle ?? null}
            entries={assetEntries()}
            collapsed={!libraryOpen()}
            onToggle={() => setLibraryOpen(!libraryOpen())}
            onPreload={(entry) => {
              preloadAsset(entry);
            }}
            onDragStart={(entry) => {
              void startAssetDrag(entry);
            }}
            onDragReturn={hideAssetDrag}
            loading={libraryLoading()}
            error={libraryError()}
            canInsert={canInsert()}
            onAdd={(entry) => void addAsset(entry)}
            onDragEnd={() => {
              if (!assetDrag?.dropped) cancelAssetDrag();
            }}
          />
          <div
            class="library-resizer"
            hidden={!libraryOpen()}
            role="separator"
            tabindex={0}
            aria-label="Resize asset library"
            aria-orientation="vertical"
            aria-valuemin={200}
            aria-valuemax={maxLibraryWidth()}
            aria-valuenow={libraryWidth()}
            onPointerDown={(event) => {
              if (event.button !== 0) return;
              event.preventDefault();
              libraryResize = {
                x: event.clientX,
                width: event.currentTarget.parentElement!.getBoundingClientRect().width,
              };
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              if (libraryResize)
                resizeLibrary(libraryResize.width + event.clientX - libraryResize.x);
            }}
            onPointerUp={(event) => {
              libraryResize = undefined;
              event.currentTarget.releasePointerCapture(event.pointerId);
            }}
            onLostPointerCapture={() => {
              libraryResize = undefined;
            }}
            onKeyDown={(event) => {
              if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
              event.preventDefault();
              resizeLibrary(
                event.key === "Home"
                  ? 200
                  : event.key === "End"
                    ? maxLibraryWidth()
                    : libraryWidth() + (event.key === "ArrowLeft" ? -16 : 16),
              );
            }}
          />
        </div>
        <div
          class={`editor-canvas ${dropActive() ? "asset-drop-active" : ""}`}
          ref={(element) => {
            viewportElement = element;
            viewport.setup(element);
          }}
          onDragOver={(event) => {
            if (event.dataTransfer?.types.includes("Files")) {
              event.preventDefault();
              event.dataTransfer.dropEffect = "copy";
              setDropActive(true);
              return;
            }
            if (!doc() || addingAsset() || !event.dataTransfer?.types.includes(ASSET_DRAG_TYPE))
              return;
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
            setDropActive(true);
            if (assetDrag) {
              assetDrag.position = viewport.assetDropPosition(event.clientX, event.clientY);
              assetDrag.inside = !!assetDrag.position;
              updateAssetDrag();
            }
          }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) hideAssetDrag();
          }}
          onDrop={(event) => {
            setDropActive(false);
            if (event.dataTransfer?.types.includes("Files")) {
              event.preventDefault();
              const files = [...event.dataTransfer.files];
              if (files.length !== 1 || !files[0]!.name.toLowerCase().endsWith(".json")) {
                props.onError("Drop one map JSON file onto the viewport.");
              } else if (!props.library()) {
                props.onError("Wait for the asset library to load before importing a map.");
              } else {
                void openMap(files[0]!.name, undefined, files[0]);
              }
              return;
            }
            const id = event.dataTransfer?.getData(ASSET_DRAG_TYPE);
            if (!id) return;
            event.preventDefault();
            const entry = assetEntries().find((entry) => entry.id === id);
            const placement = viewport.assetDropPosition(event.clientX, event.clientY);
            if (assetDrag && entry?.id === assetDrag.entry.id && placement) {
              assetDrag.position = placement;
              assetDrag.inside = true;
              assetDrag.dropped = true;
              updateAssetDrag();
            } else if (entry && placement) void addAsset(entry, placement);
          }}
        >
          <Show when={!doc() && !mapLoadProgress()}>
            <div class="viewport-welcome">
              <span class="eyebrow">MAP WORKSPACE</span>
              <h2>{props.library() ? "Choose a map to begin" : "Build your world"}</h2>
              <p>
                {props.library()
                  ? maps().length
                    ? "Choose a map above, or create a new map to start from scratch."
                    : "This library has no maps yet. Use New map to create your first scene."
                  : "Loading maps and reusable assets… Game data is optional for mission previews."}
              </p>
              <div class="welcome-steps">
                <span>01 · Choose a map or create one</span>
                <span>02 · Place assets</span>
                <span>03 · Save or download</span>
              </div>
            </div>
          </Show>
          <Show when={helpOpen()}>
            <div id="editor-help" class="viewport-help">
              <div class="detail-head">
                <h2>Viewport controls</h2>
                <button aria-label="Close help" onClick={() => setHelpOpen(false)}>
                  ×
                </button>
              </div>
              <dl>
                <dt>Select / move</dt>
                <dd>Click / drag object</dd>
                <dt>Select a part</dt>
                <dd>Alt-click</dd>
                <dt>Pan / orbit</dt>
                <dd>Left / right drag</dd>
                <dt>Zoom</dt>
                <dd>Mouse wheel</dd>
                <dt>Frame / game view</dt>
                <dd>F / G</dd>
                <dt>Rotate</dt>
                <dd>Q / E</dd>
                <dt>Duplicate / delete</dt>
                <dd>D / Delete</dd>
                <dt>Save / undo</dt>
                <dd>Ctrl or ⌘ + S / Z</dd>
              </dl>
            </div>
          </Show>
        </div>
        <aside class="editor-panel" aria-label="Inspector">
          <nav class="inspector-tabs" aria-label="Inspector sections">
            <For each={["Selection", "Draw", "View"]}>
              {(name) => (
                <button
                  aria-pressed={panel() === name ? "true" : "false"}
                  class={panel() === name ? "selected" : ""}
                  disabled={editingPath() && name !== "Draw"}
                  title={
                    editingPath() && name !== "Draw"
                      ? "Finish or cancel the path before switching tools"
                      : undefined
                  }
                  onClick={() => setPanel(name)}
                >
                  {name}
                </button>
              )}
            </For>
          </nav>
          <div class="inspector-content" hidden={panel() !== "Draw"}>
            <p class="panel-intro">
              Draw walls, rivers and paths directly in the scene. Finish or cancel a path before
              switching tools.
            </p>
            <SplinePanel
              document={doc}
              library={() => props.library()?.handle ?? null}
              entries={assetEntries}
              viewport={viewport}
              commit={pushHistory}
              onError={props.onError}
              active={panel() === "Draw"}
              onEditingChange={setEditingPath}
            />
          </div>
          <div class="inspector-content" hidden={panel() !== "View"}>
            <section class="view-settings">
              <h2>Camera &amp; display</h2>
              <div class="view-overlays">
                <label class="check">
                  <input
                    type="checkbox"
                    checked={showObstacles()}
                    onChange={(e) => setShowObstacles(e.currentTarget.checked)}
                  />{" "}
                  Obstacles
                </label>
                <label class="check">
                  <input
                    type="checkbox"
                    checked={showElevation()}
                    onChange={(e) => setShowElevation(e.currentTarget.checked)}
                  />{" "}
                  Elevation lines
                </label>
              </div>
              <label class="perspective-control">
                <span>
                  Perspective{" "}
                  <output>{perspective() === 0 ? "Orthographic" : `${perspective()}°`}</output>
                </span>
                <input
                  aria-label="Perspective"
                  type="range"
                  min="0"
                  max="65"
                  step="1"
                  value={perspective()}
                  onInput={(e) => setPerspective(Number(e.currentTarget.value))}
                />
              </label>
              <p class="hint">
                Increase perspective for depth and distance scaling. Orbit to view characters from
                different sides and heights.
              </p>
              <label class="check">
                <input
                  type="checkbox"
                  checked={rotationSnap()}
                  onChange={(e) => setRotationSnap(e.currentTarget.checked)}
                />{" "}
                Lock rotation to 16 angles
              </label>
              <label class="check">
                <input
                  type="checkbox"
                  checked={spriteOrientationLock()}
                  onChange={(e) => setSpriteOrientationLock(e.currentTarget.checked)}
                />{" "}
                Lock sprite orientations
              </label>
              <p class="hint">
                Off: sprites face the camera. On: sprites use fixed 22.5° projection angles. Prone
                characters always stay locked.
              </p>
              <label class="check">
                <input
                  type="checkbox"
                  checked={showEntities()}
                  onChange={(e) => setShowEntities(e.currentTarget.checked)}
                />{" "}
                Mission entities
              </label>
              <label class="check">
                <input
                  type="checkbox"
                  checked={smoothTextures()}
                  onChange={(e) => setSmoothTextures(e.currentTarget.checked)}
                />{" "}
                Smooth textures
              </label>
              <label class="check">
                <input
                  type="checkbox"
                  checked={synthesizedTextures()}
                  onChange={(e) => setSynthesizedTextures(e.currentTarget.checked)}
                />{" "}
                Synthesized hidden surfaces
              </label>
              <For
                each={(() => {
                  doc();
                  patchPreviewRevision();
                  return viewport.patchPreviews();
                })()}
              >
                {(patch) => (
                  <label class="check">
                    <input
                      type="checkbox"
                      checked={patch.revealed}
                      onChange={(event) => {
                        viewport.setPatchRevealed(patch.id, event.currentTarget.checked);
                        setPatchPreviewRevision((value) => value + 1);
                      }}
                    />{" "}
                    Reveal interior: {patch.name}
                  </label>
                )}
              </For>
              <Show when={doc()?.population}>
                {(population) => (
                  <details>
                    <summary>
                      Town population — {population().actors.length} people,{" "}
                      {population().items.length} items
                    </summary>
                    <label class="check">
                      <input
                        type="checkbox"
                        checked={populationPlaying()}
                        onChange={(e) => {
                          setPopulationPlaying(e.currentTarget.checked);
                          viewport.setPopulationPlaying(e.currentTarget.checked);
                        }}
                      />{" "}
                      Animate routines and patrols
                    </label>
                    <label class="check">
                      <input
                        type="checkbox"
                        checked={populationRoutes()}
                        onChange={(e) => {
                          setPopulationRoutes(e.currentTarget.checked);
                          viewport.setPopulationRoutesVisible(e.currentTarget.checked);
                        }}
                      />{" "}
                      Show patrol and civilian routes
                    </label>
                    <p class="hint">
                      Preview of authored routines. Combat, dialogue and item collection require a
                      playable mission export.
                    </p>
                    <For each={population().actors}>
                      {(actor) => (
                        <details>
                          <summary>{actor.name}</summary>
                          <p>{actor.duty}</p>
                          <Show when={actor.information}>
                            <p>{actor.information}</p>
                          </Show>
                        </details>
                      )}
                    </For>
                    <For each={population().items}>
                      {(item) => (
                        <p>
                          {item.name} ×{item.quantity} — {item.purpose}
                        </p>
                      )}
                    </For>
                  </details>
                )}
              </Show>
              <Show when={missionName()}>
                <p class="mission-summary">
                  {missionName()} — {missionInfo()}
                </p>
                <p class="hint">
                  Initial placements; mission scripts are not run. Green markers show spawn points.
                  Magenta markers indicate missing sprite assets. Standing characters, prone bodies,
                  pickups, and scenery use different depth profiles.
                </p>
              </Show>
            </section>
            <LightingPanel document={doc} commit={pushHistory} />
            <section class="view-settings export-settings">
              <h2>Export frame</h2>
              <p class="hint">
                An optional crop for compilation. Assets remain editable outside the frame,
                including parts you intend to crop.
              </p>
              <div class="row">
                <button
                  disabled={!doc()}
                  onClick={() => {
                    try {
                      pushHistory({ ...doc()!, exportBounds: viewport.fitExportBounds() });
                    } catch (error) {
                      props.onError(String(error));
                    }
                  }}
                >
                  {doc()?.exportBounds ? "Fit to content" : "Set export frame"}
                </button>
                <Show when={doc()?.exportBounds}>
                  <button onClick={() => pushHistory({ ...doc()!, exportBounds: undefined })}>
                    Remove frame
                  </button>
                </Show>
              </div>
              <Show when={doc()?.exportBounds}>
                {(bounds) => (
                  <div class="export-fields">
                    <For each={["Left", "Top", "Width", "Height"]}>
                      {(label, index) => (
                        <label>
                          {label}
                          <input
                            type="number"
                            aria-label={`Export ${label.toLowerCase()}`}
                            step="1"
                            min={index() > 1 ? 1 : undefined}
                            value={bounds()[index()]}
                            onChange={(event) => {
                              const value = Number(event.currentTarget.value);
                              if (
                                !event.currentTarget.value ||
                                !Number.isInteger(value) ||
                                (index() > 1 && value < 1)
                              ) {
                                event.currentTarget.value = String(bounds()[index()]);
                                return;
                              }
                              const next = [...bounds()] as [number, number, number, number];
                              next[index()] = value;
                              pushHistory({ ...doc()!, exportBounds: next });
                            }}
                          />
                        </label>
                      )}
                    </For>
                  </div>
                )}
              </Show>
              <Show when={!doc()?.exportBounds}>
                <p class="hint">No custom crop set.</p>
              </Show>
            </section>
          </div>
          <div class="inspector-content" hidden={panel() !== "Selection"}>
            <h2 class="panel-title">Selection</h2>
            <Show
              when={selectedTransform()}
              fallback={
                <p class="hint">
                  Select an object in the scene or the list below to edit its properties. Alt-click
                  to select a single part.
                </p>
              }
            >
              {(t) => (
                <section class="object-detail">
                  <h2>{selectionTitle()}</h2>
                  <Show when={selectedPart()}>
                    {(p) => (
                      <>
                        <div class="meta-row">
                          <span class="meta-key">source</span>
                          <span>
                            {p().source.map}{" "}
                            {p().kind === "scenery"
                              ? "scenery"
                              : (p().source.mission_profile ?? `#${p().source.obstacle}`)}
                          </span>
                        </div>
                        <Show when={p().obstacle}>
                          {(ob) => (
                            <>
                              <div class="meta-row">
                                <span class="meta-key">flags</span>
                                <span>
                                  {ob().opaque ? "opaque " : "clear "}
                                  {(ob() as unknown as { solid?: boolean }).solid ? "solid" : ""}
                                </span>
                              </div>
                              <div class="meta-row">
                                <span class="meta-key">height</span>
                                <span>
                                  {Math.round(Math.min(...ob().points.map((q) => q.z_bottom)))}–
                                  {Math.round(Math.max(...ob().points.map((q) => q.z_top)))}
                                </span>
                              </div>
                            </>
                          )}
                        </Show>
                        <Show when={p().group}>
                          {(g) => (
                            <button onClick={() => select({ kind: "group", id: g() })}>
                              Select building {g()}
                            </button>
                          )}
                        </Show>
                        <Show
                          when={(() => {
                            const index = p().source.obstacle;
                            return index === undefined ? undefined : suspects().get(index);
                          })()}
                        >
                          {(sus) => (
                            <div class="row suspect">
                              <span class="hint">
                                Floats {Math.round(sus().delta)} above #{sus().support}; may be
                                stored displaced along the view ray (same map pixels).
                              </span>
                              <button
                                onClick={() => {
                                  const t = p().transform;
                                  setTransform({
                                    ...t,
                                    dy: t.dy - sus().delta,
                                    dz: t.dz - sus().delta,
                                  });
                                }}
                              >
                                Snap down {Math.round(sus().delta)}
                              </button>
                            </div>
                          )}
                        </Show>
                      </>
                    )}
                  </Show>
                  <h3>
                    Transform
                    {selectedPart()?.group ? " (within the building)" : ""}
                  </h3>
                  <For each={["dx", "dy", "dz", "rot_deg"] as const}>
                    {(f) => (
                      <div class="meta-row">
                        <span class="meta-key">
                          {
                            {
                              dx: "Offset X",
                              dy: "Offset Y",
                              dz: "Height offset",
                              rot_deg: "Rotation (°)",
                            }[f]
                          }
                        </span>
                        <ScrubNumber
                          label={
                            {
                              dx: "Offset X",
                              dy: "Offset Y",
                              dz: "Height offset",
                              rot_deg: "Rotation (°)",
                            }[f]
                          }
                          step={f === "rot_deg" ? 5 : 1}
                          value={t()[f]}
                          onPreview={(value) => previewTransformField(f, value)}
                          onCommit={(value) => setTransformField(f, value)}
                          onCancel={() => {
                            if (!disposed && doc()) viewport.syncViews(doc()!, false);
                          }}
                        />
                      </div>
                    )}
                  </For>
                  <div class="row">
                    <button onClick={() => rotateSelected(-15)} title="q">
                      ⟲ 15°
                    </button>
                    <button onClick={() => rotateSelected(15)} title="e">
                      ⟳ 15°
                    </button>
                    <label class="check inline">
                      <input
                        type="checkbox"
                        checked={gizmoVertical()}
                        onChange={(e) => setGizmoVertical(e.currentTarget.checked)}
                      />{" "}
                      lift
                    </label>
                  </div>
                  <Show when={selectedGroup()?.states}>
                    <label>
                      State{" "}
                      <select
                        value={selectedGroup()?.states?.active}
                        onChange={(event) =>
                          pushHistory(
                            setGroupState(
                              doc()!,
                              selectedGroup()!.id,
                              event.currentTarget.value as "initial" | "applied",
                            ),
                          )
                        }
                      >
                        <option value="initial">Initial</option>
                        <option value="applied">Applied</option>
                      </select>
                    </label>
                  </Show>
                  <Show when={selectedStatePart()}>
                    <p>Select the whole group to change its state, duplicate it, or delete it.</p>
                  </Show>
                  <div class="row">
                    <button onClick={duplicateSelected} title="d" disabled={!!selectedStatePart()}>
                      Duplicate
                    </button>
                    <button onClick={deleteSelected} title="del" disabled={!!selectedStatePart()}>
                      Delete
                    </button>
                    <button onClick={() => setTransform({ ...IDENTITY_TRANSFORM })}>Reset</button>
                    <label class="check inline">
                      <input
                        type="checkbox"
                        checked={!!(selectedGroup()?.hidden ?? selectedPart()?.hidden)}
                        disabled={!!selectedStatePart()}
                        onChange={(e) => setHidden(e.currentTarget.checked)}
                      />{" "}
                      hidden
                    </label>
                  </div>
                </section>
              )}
            </Show>
            <section class="object-list">
              <h3>
                Scene objects <span class="object-count">{doc()?.objects.length ?? 0}</span>
              </h3>
              <div class="search-row">
                <input
                  class="search"
                  aria-label="Find scene objects"
                  placeholder="Find objects…"
                  value={filter()}
                  onInput={(e) => setFilter(e.currentTarget.value)}
                />
              </div>
              <Show when={doc() && !rows().length}>
                <p class="hint">
                  {filter()
                    ? "No objects match your search."
                    : "Your scene has no objects yet. Add one from Assets."}
                </p>
              </Show>
              <ul>
                <For each={rows()}>
                  {(r) => (
                    <li
                      class={`${isSelected(r) ? "selected" : ""} ${r.hidden ? "hidden" : ""} depth-${r.depth}`}
                      tabindex={0}
                      role="button"
                      aria-pressed={isSelected(r) ? "true" : "false"}
                      title={r.label}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          select({ kind: r.kind, id: r.id });
                        }
                      }}
                      onClick={() => select({ kind: r.kind, id: r.id })}
                    >
                      <Show
                        when={r.kind === "group"}
                        fallback={
                          <span class="kind">{r.id.startsWith("terrace") ? "▬" : "·"}</span>
                        }
                      >
                        <span
                          class="chev-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleExpanded(r.id);
                          }}
                        >
                          {expanded().has(r.id) ? "▾" : "▸"}
                        </span>
                      </Show>
                      {r.label}
                      <Show when={r.parts !== undefined}>
                        <span class="count">{r.parts}</span>
                      </Show>
                      <Show when={r.moved}>
                        <span class="tag">moved</span>
                      </Show>
                      <Show when={r.suspect}>
                        <span
                          class="tag suspect"
                          title="may float: stored displaced along the view ray"
                        >
                          float?
                        </span>
                      </Show>
                    </li>
                  )}
                </For>
              </ul>
            </section>
          </div>
        </aside>
      </div>
      <footer class="editor-footer">
        <span class="document-state">
          {mapName() ? mapLabel(mapName()!) : "No map open"}
          {doc() ? (dirty() ? " · Unsaved changes" : " · Saved") : ""}
        </span>
        <span class="editor-status" role="status">
          {info()}
        </span>
        <span class="footer-hint">Drag to pan · Right-drag to orbit · Scroll to zoom</span>
      </footer>
    </div>
  );
}
