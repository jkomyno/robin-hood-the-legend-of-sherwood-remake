# Publishing the editor and library

From `level-editor/`, run:

```sh
pnpm library:publish
pnpm editor:publish
```

These deploy two static-asset Workers using the pinned Wrangler dependency in
`../wasm-www` (install that project's dependencies first if needed):

| Worker | Routes |
| --- | --- |
| `robinhood-editor-library` | `robinhood.phiresky.xyz/editor/library` and `/editor/library/*` |
| `robinhood-editor` | `robinhood.phiresky.xyz/editor` and `/editor/*` |

The editor build uses `/editor/` as its base and loads the library from
`/editor/library/`. The more specific library route takes precedence. Wrangler
attaches the routes in the `phiresky.xyz` zone; the hostname must already have
proxied DNS. Neither Worker exposes a workers.dev URL. The game deployment's
route checker accepts these independently managed routes when present.

Authenticate with `pnpm --dir ../wasm-www exec wrangler login`, or provide
`CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` in the environment. The token
needs Workers deployment and zone route editing permissions.

Both commands accept `--stage-only` to build an offline snapshot, `--dry-run` to
also validate through Wrangler without uploading, and `--output <fresh-dir>`.
Each run otherwise creates a fresh snapshot in `work/library-publish/` or
`work/editor-publish/`. The generated `wrangler.json` and `site/` are reviewable
before deployment. To deploy an existing reviewed snapshot:

```sh
pnpm --dir ../wasm-www exec wrangler deploy --config /absolute/path/to/deploy/wrangler.json
```

Library publication regenerates the catalog from directory descriptors and
fails for missing or stale lossy models, external runtime GLB resources, stale
map pins, or files exceeding Cloudflare's static asset limits. It uploads only:

- Optimized models, palette previews, and asset descriptors.
- A generated asset catalog containing verified original-model hashes.
- Published maps and their generated listing.
- Population sprite catalogs filtered to referenced sprites, and those images.

Original models, receipts, source textures/buffers, backups, blobs, and authoring
files are excluded. Original paths and hashes remain identities in descriptors
and saved maps; the editor renders optimized models without fetching originals.
The source library is never modified. `report.json` records each uploaded
payload's hash and size and remains outside the public assets directory.

Cloudflare references: [subdirectory asset routing](https://developers.cloudflare.com/workers/static-assets/routing/advanced/serving-a-subdirectory/),
[Worker routes](https://developers.cloudflare.com/workers/configuration/routing/routes/),
[static asset limits](https://developers.cloudflare.com/workers/platform/limits/).
