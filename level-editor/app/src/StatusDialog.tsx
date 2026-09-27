import { Show } from "solid-js";

/** Progress and completion messages share a modal, never a row in the toolbar. */
export default function StatusDialog(props: {
  message: string;
  busy: boolean;
  onClose: () => void;
}) {
  return (
    <dialog
      class="status-dialog"
      aria-labelledby="editor-status-title"
      aria-describedby="editor-status-message"
      ref={(dialog) =>
        queueMicrotask(() => {
          if (dialog.isConnected) dialog.showModal();
        })
      }
      onCancel={(event) => {
        event.preventDefault();
        if (!props.busy) props.onClose();
      }}
    >
      <h2 id="editor-status-title">{props.busy ? "Working…" : "Complete"}</h2>
      <p id="editor-status-message" role="status" aria-live="polite">
        {props.message}
      </p>
      <Show when={props.busy} fallback={<button onClick={props.onClose}>Close</button>}>
        <progress aria-label="Operation in progress" />
      </Show>
    </dialog>
  );
}
