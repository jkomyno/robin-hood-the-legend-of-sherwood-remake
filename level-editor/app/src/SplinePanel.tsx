import { For, Show, createEffect, createSignal, onCleanup } from "solid-js";
import { parseLevel3D, type ExternalAssetSource, type Level3D, type LevelSpline, type ProjectionAssetEntry, type Vec3 } from "@rle/shared";
import type { EditorViewport } from "./editor-viewport";
import { prepareProjectionAsset } from "./projection-library";
import { disposeObjectResources } from "./resources";
import { splineCurve } from "./spline-geometry";
import { assetType } from "./asset-library";

export default function SplinePanel(props: {
  document: () => Level3D | null;
  library: () => FileSystemDirectoryHandle | null;
  entries: () => ProjectionAssetEntry[];
  viewport: EditorViewport;
  commit(document: Level3D): void;
  onError(message: string): void;
}) {
  const [active, setActive] = createSignal("");
  const [draft, setDraft] = createSignal<LevelSpline | null>(null);
  const [point, setPoint] = createSignal(0);
  const [wallSource, setWallSource] = createSignal("");
  const [busy, setBusy] = createSignal(false);
  let pendingSource: ExternalAssetSource | undefined;
  let disposed = false;
  let attempt = 0;
  const path = () => draft() ?? props.document()?.splines?.find(path => path.id === active()) ?? null;
  const sources = () => props.entries().filter(entry => entry.editor_usage !== "map-background")
    .sort((a, b) => Number(assetType(b) === "Wall") - Number(assetType(a) === "Wall") || a.name.localeCompare(b.name));
  function exit() {
    setActive(""); setDraft(null); setPoint(0); pendingSource = undefined;
    props.viewport.setSplineEdit(null);
  }
  function publish(next: Level3D) {
    try { parseLevel3D(next); props.commit(next); return true; }
    catch (error) { props.onError(String(error)); return false; }
  }
  function change(next: LevelSpline) {
    const document = props.document();
    if (!document) return;
    if (!Number.isFinite(next.width) || next.width <= 0 || !Number.isFinite(next.repeatLength) || next.repeatLength < 1 ||
        next.points.some(p => p.some(v => !Number.isFinite(v))) ||
        !Number.isFinite(next.sourceAngle ?? 0) ||
        (next.kind === "wall" && ((next.sourceStart ?? 0) < 0 || (next.sourceEnd ?? 1) > 1 ||
          (next.sourceEnd ?? 1) - (next.sourceStart ?? 0) < 0.05))) {
      props.onError("Use positive width/repeat values and retain at least 5% of the source segment");
      return;
    }
    if (next.kind === "wall" && next.points.length >= 2 && splineCurve(next, document.camera).getLength() / next.repeatLength > 512) {
      props.onError("Increase repeat length: a wall path supports at most 512 repeats");
      return;
    }
    if (draft()) { setDraft(next); return; }
    if (document) publish({ ...document, splines: document.splines?.map(path => path.id === next.id ? next : path) });
  }
  function patch(values: Partial<LevelSpline>) {
    const current = path();
    if (current) change({ ...current, ...values });
  }
  function move(index: number, position: Vec3) {
    const current = path();
    if (current) patch({ points: current.points.map((p, i) => i === index ? position : p) });
  }
  async function begin(kind: "river" | "wall") {
    const document = props.document(), root = props.library();
    if (!document || !root || busy()) return;
    const token = ++attempt;
    setBusy(true);
    let prepared: Awaited<ReturnType<typeof prepareProjectionAsset>> | null = null;
    try {
      let reference: ExternalAssetSource | undefined;
      let wallWidth = 35, wallRepeat = 180, sourceAngle = 0;
      if (kind === "wall") {
        const entry = sources().find(entry => entry.id === wallSource()) ?? sources()[0];
        if (!entry) throw new Error("Publish a wall asset to the shared library first");
        prepared = await prepareProjectionAsset(root, entry, document.map);
        if (disposed || token !== attempt || document !== props.document() || root !== props.library()) return;
        const existing = document.assetSources?.find(source => source.id === entry.id);
        if (existing && (existing.model_sha256 !== prepared.reference.model_sha256 || existing.descriptor_sha256 !== prepared.reference.descriptor_sha256))
          throw new Error("The scene already uses a different revision of this asset");
        reference = prepared.reference;
        const vertices = prepared.descriptor.parts.flatMap(part => part.obstacle_local_game.points)
          .map(p => [p.x, -p.y / Math.sin(document.camera.elevation_deg * Math.PI / 180)]);
        const cx = vertices.reduce((sum, p) => sum + p[0]!, 0) / vertices.length;
        const cy = vertices.reduce((sum, p) => sum + p[1]!, 0) / vertices.length;
        let xx = 0, xy = 0, yy = 0;
        for (const p of vertices) { const x = p[0]! - cx, y = p[1]! - cy; xx += x*x; xy += x*y; yy += y*y; }
        const angle = 0.5 * Math.atan2(2 * xy, xx - yy);
        sourceAngle = angle * 180 / Math.PI;
        const along = vertices.map(p => p[0]! * Math.cos(angle) + p[1]! * Math.sin(angle));
        const across = vertices.map(p => -p[0]! * Math.sin(angle) + p[1]! * Math.cos(angle));
        wallRepeat = Math.max(1, Math.round(Math.max(...along) - Math.min(...along)));
        wallWidth = Math.max(1, Math.round(Math.max(...across) - Math.min(...across)));
        if (!props.viewport.adoptAsset(reference, prepared.asset, prepared.sources)) disposeObjectResources([prepared.asset]);
        prepared = null;
        setWallSource(entry.id);
      }
      exit();
      pendingSource = reference;
      setDraft({
        id: "path-" + crypto.randomUUID(), name: kind === "river" ? "River" : "Battlement wall", kind,
        points: [], closed: false, width: kind === "river" ? 110 : wallWidth, repeatLength: kind === "river" ? 150 : wallRepeat,
        ...(reference ? { asset: reference.id, axis: "x" as const, sourceAngle, sourceStart: 0, sourceEnd: 1 } : {}),
      });
    } catch (error) { props.onError(String(error)); }
    finally {
      if (prepared) disposeObjectResources([prepared.asset]);
      if (!disposed) setBusy(false);
    }
  }
  function finish() {
    const current = draft(), document = props.document();
    if (!current || !document || current.points.length < (current.closed ? 3 : 2)) return;
    const assetSources = pendingSource && !document.assetSources?.some(source => source.id === pendingSource!.id)
      ? [...(document.assetSources ?? []), pendingSource] : document.assetSources;
    if (publish({ ...document, assetSources, splines: [...(document.splines ?? []), current] })) {
      setActive(current.id); setDraft(null); pendingSource = undefined;
    }
  }
  function removePoint() {
    const current = path();
    if (!current || current.points.length <= (draft() ? 0 : current.closed ? 3 : 2)) return;
    const index = Math.min(point(), current.points.length - 1);
    patch({ points: current.points.filter((_, i) => i !== index) });
    setPoint(Math.max(0, index - 1));
  }
  createEffect(() => props.document()?.map, () => { attempt++; exit(); });
  createEffect(() => ({ current: path(), selected: point(), drawing: !!draft() }), ({ current, selected, drawing }) => {
    props.viewport.setSplineEdit(current ? {
      path: current, point: selected, drawing,
      append(position) {
        const last = current.points.at(-1);
        if (last && Math.hypot(last[0] - position[0], last[1] - position[1]) < 1) return;
        if (current.points.length >= 256) { props.onError("A path supports at most 256 control points"); return; }
        patch({ points: [...current.points, position] });
        setPoint(current.points.length);
      },
      move, selectPoint: setPoint,
    } : null);
  });
  const onKey = (event: KeyboardEvent) => {
    if (!path() || (event.target instanceof HTMLElement && (event.target.isContentEditable || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)))) return;
    if (event.key === "Escape") { event.stopImmediatePropagation(); event.preventDefault(); exit(); }
    else if (event.key === "Enter" && draft()) { event.stopImmediatePropagation(); event.preventDefault(); finish(); }
    else if (event.key === "Delete" || event.key === "Backspace") { event.stopImmediatePropagation(); event.preventDefault(); removePoint(); }
  };
  window.addEventListener("keydown", onKey, true);
  onCleanup(() => { disposed = true; attempt++; window.removeEventListener("keydown", onKey, true); props.viewport.setSplineEdit(null); });
  return <section class="spline-panel">
    <h2>Paths</h2>
    <div class="spline-actions">
      <button disabled={!props.document() || busy()} onClick={() => void begin("river")}>Draw river</button>
      <button disabled={!props.document() || busy() || !sources().length} onClick={() => void begin("wall")}>Draw wall</button>
    </div>
    <label>Wall asset<select aria-label="Wall path asset" value={wallSource()} onChange={event => setWallSource(event.currentTarget.value)}>
      <option value="">Choose a wall segment…</option>
      <For each={sources()}>{entry => <option value={entry.id}>{entry.name} · {entry.source_map}</option>}</For>
    </select></label>
    <div class="spline-list"><For each={props.document()?.splines ?? []}>{item =>
      <button class={active() === item.id ? "selected" : ""} onClick={() => { setDraft(null); setActive(item.id); setPoint(0); }}>{item.name} · {item.kind}</button>
    }</For></div>
    <Show when={path()}>{current => <>
      <p class="hint">{draft() ? "Click the ground to add points. Enter finishes; Escape cancels." : "Drag the cyan control points. Right drag orbits; click elsewhere to pan."}</p>
      <label>Name<input aria-label="Path name" value={current().name} onChange={event => patch({ name: event.currentTarget.value })} /></label>
      <div class="spline-fields">
        <label>Width<input type="number" aria-label="Path width" min="1" step="5" value={current().width}
          onChange={event => patch({ width: Number(event.currentTarget.value) })} /></label>
        <label>Repeat length<input type="number" aria-label="Path repeat length" min="1" step="5" value={current().repeatLength}
          onChange={event => patch({ repeatLength: Number(event.currentTarget.value) })} /></label>
      </div>
      <label class="check"><input type="checkbox" checked={current().closed} disabled={current().points.length < 3}
        onChange={event => patch({ closed: event.currentTarget.checked })} /> Closed loop</label>
      <Show when={current().kind === "wall"}>
        <label class="check"><input type="checkbox" aria-label="Flip battlement side" checked={current().flipCrossSection ?? false}
          onChange={event => patch({ flipCrossSection: event.currentTarget.checked })} /> Flip battlement side</label>
        <label>Source direction<select aria-label="Wall source direction" value={current().axis}
          onChange={event => patch({ axis: event.currentTarget.value as "x" | "y" })}><option value="x">Along X</option><option value="y">Along Y</option></select></label>
        <label>Source alignment angle<input type="number" step="1" value={current().sourceAngle ?? 0}
          onChange={event => patch({ sourceAngle: Number(event.currentTarget.value) })} /></label>
        <div class="spline-fields">
          <label>Trim start %<input type="number" min="0" max="95" value={(current().sourceStart ?? 0) * 100}
            onChange={event => patch({ sourceStart: Number(event.currentTarget.value) / 100 })} /></label>
          <label>Trim end %<input type="number" min="5" max="100" value={(current().sourceEnd ?? 1) * 100}
            onChange={event => patch({ sourceEnd: Number(event.currentTarget.value) / 100 })} /></label>
        </div>
      </Show>
      <Show when={current().kind === "river"}>
        <label>River texture tile<input type="file" accept="image/png,image/jpeg,image/webp" onChange={event => {
          const file = event.currentTarget.files?.[0], id = current().id;
          if (!file) return;
          if (file.size > 8 * 1024 * 1024) { props.onError("Use a tile smaller than 8 MB"); return; }
          const reader = new FileReader();
          reader.onload = () => { if (!disposed && path()?.id === id) patch({ texture: String(reader.result) }); };
          reader.onerror = () => props.onError("Could not read river texture");
          reader.readAsDataURL(file);
        }} /></label>
        <Show when={current().texture}><button onClick={() => patch({ texture: undefined })}>Use default river tile</button></Show>
      </Show>
      <div class="spline-points"><For each={current().points}>{(_, index) =>
        <button class={point() === index() ? "selected" : ""} onClick={() => setPoint(index())}>{index() + 1}</button>
      }</For></div>
      <Show when={current().points[point()]}>{position =>
        <div class="spline-coordinates"><For each={["X", "Y", "Z"]}>{(label, axis) =>
          <label>{label}<input type="number" step="1" aria-label={"Control point " + label} value={Math.round(position()[axis()]! * 10) / 10}
            onChange={event => { const value: Vec3 = [...position()]; value[axis()] = Number(event.currentTarget.value); move(point(), value); }} /></label>
        }</For></div>
      }</Show>
      <div class="spline-actions">
        <button disabled={current().points.length < 2} onClick={() => {
          const points = current().points, index = Math.min(point(), points.length - 2);
          const a = points[index]!, b = points[index + 1]!;
          patch({ points: [...points.slice(0, index + 1), a.map((v, i) => (v + b[i]!) / 2) as Vec3, ...points.slice(index + 1)] });
          setPoint(index + 1);
        }}>Insert point</button>
        <button onClick={removePoint}>Remove point</button>
      </div>
      <div class="spline-actions">
        <Show when={draft()} fallback={<button onClick={exit}>Done editing</button>}>
          <button disabled={current().points.length < (current().closed ? 3 : 2)} onClick={finish}>Finish path</button>
          <button onClick={exit}>Cancel</button>
        </Show>
        <Show when={!draft()}><button onClick={() => {
          const document = props.document();
          if (document && publish({ ...document, splines: document.splines?.filter(item => item.id !== current().id) })) exit();
        }}>Delete path</button></Show>
      </div>
    </>}</Show>
  </section>;
}
