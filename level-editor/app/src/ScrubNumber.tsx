import { createSignal, onCleanup } from "solid-js";
import type { JSX } from "@solidjs/web";

/** Preview while dragging; commit one edit on release. A click still permits typing. */
export default function ScrubNumber(props: {
  label: string;
  labelExtra?: () => JSX.Element;
  value: number;
  step: number;
  onPreview: (value: number) => void;
  onCommit: (value: number) => void;
  onCancel: () => void;
}) {
  const [preview, setPreview] = createSignal<number | null>(null);
  const [editing, setEditing] = createSignal(false);
  let gesture: { x: number; value: number; current: number; moved: boolean } | null = null;
  function cancel() {
    if (gesture?.moved) props.onCancel();
    gesture = null;
    setPreview(null);
  }
  onCleanup(cancel);
  return (
    <div
      class="meta-row scrub-number"
      onDragStart={(event) => event.preventDefault()}
      title="Drag left or right to adjust; hold Shift for finer control. Click to type."
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        gesture = { x: event.clientX, value: props.value, current: props.value, moved: false };
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (!gesture) return;
        const delta = event.clientX - gesture.x;
        if (!gesture.moved && Math.abs(delta) < 4) return;
        gesture.moved = true;
        event.preventDefault();
        const value = Math.round((gesture.value + delta * (event.shiftKey ? 0.1 : 1)) * 100) / 100;
        gesture.current = value;
        setPreview(value);
        props.onPreview(value);
      }}
      onPointerUp={(event) => {
        const value = gesture?.current,
          initial = gesture?.value,
          moved = gesture?.moved;
        gesture = null;
        setPreview(null);
        if (moved && value !== undefined) {
          event.preventDefault();
          if (value !== initial) props.onCommit(value);
          else props.onCancel();
        }
        event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onPointerCancel={cancel}
      onLostPointerCapture={cancel}
      onKeyDown={(event) => {
        if (event.key === "Escape" && gesture) {
          event.preventDefault();
          event.stopPropagation();
          cancel();
        }
      }}
    >
      <span class="meta-key" style={{ "user-select": "none" }}>
        {props.label}{" "}
        {props.labelExtra?.()}
      </span>
      <input
        class="scrub-number"
        type="number"
        aria-label={props.label}
        step={props.step}
        value={editing() ? (preview() ?? props.value) : (preview() ?? props.value).toFixed(2)}
        onFocus={() => setEditing(true)}
        onBlur={() => setEditing(false)}
        onChange={(event) => {
          const value = event.currentTarget.valueAsNumber;
          if (!gesture?.moved && Number.isFinite(value)) props.onCommit(value);
        }}
      />
    </div>
  );
}
