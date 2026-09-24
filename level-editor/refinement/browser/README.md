# Publication browser verification

Prepare a hash-pinned config with `../prepare_publication_browser.py`, then run:

```sh
node level-editor/refinement/browser/verify_publication.mjs config.json http://127.0.0.1:5180
```

The harness copies only the declared inputs into a fresh Chromium profile's
private OPFS library. It checks the production loader and state predicates,
then uses the actual editor to insert every eligible asset, select it, edit its
placement, save, duplicate, undo/redo and reload. The live library is read-only;
all its JSON and GLB hashes are checked before and after the run.

`progress.json` records the current phase. `result.json` starts as `RUNNING` and
ends with a functional verdict. Inspect the covered/revealed screenshots before
issuing a combined visual verdict. Run expensive Blender verification serially
with the browser when host memory is constrained.

An optional config `viewport: {"width": 2100, "height": 1200}` gives the shared
asset-library sidebar and the entire map room in an overview screenshot.
`visual_only: true` produces supplemental covered/revealed screenshots and
explicitly labels its receipt; it does not replace the full insertion/reload
verification. No renderer or scene overrides are injected.
