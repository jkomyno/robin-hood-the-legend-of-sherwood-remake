/** Native modal keeps focus and errors above the editor without changing its layout. */
export default function ErrorDialog(props: { message: string; onClose: () => void }) {
  return (
    <dialog
      class="error-dialog"
      aria-labelledby="editor-error-title"
      aria-describedby="editor-error-message"
      ref={(dialog) =>
        queueMicrotask(() => {
          if (dialog.isConnected) dialog.showModal();
        })
      }
      onCancel={(event) => {
        event.preventDefault();
        props.onClose();
      }}
    >
      <h2 id="editor-error-title">Error</h2>
      <p id="editor-error-message" role="alert">
        {props.message}
      </p>
      <button onClick={props.onClose}>Close</button>
    </dialog>
  );
}
