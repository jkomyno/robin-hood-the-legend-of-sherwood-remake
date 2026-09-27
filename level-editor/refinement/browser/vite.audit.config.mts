/** Editor dev server for publication audits: a private port and no file watching, so
 * concurrent editor edits cannot hot-reload the page (and close the map) mid-audit. */
import { fileURLToPath } from "node:url";
import base from "../../app/vite.config.ts";

const port = Number(process.env.AUDIT_PORT ?? 5181);
export default {
  ...base,
  root: fileURLToPath(new URL("../../app/", import.meta.url)),
  server: { ...base.server, port, strictPort: true, host: "127.0.0.1", hmr: false, watch: null },
};
