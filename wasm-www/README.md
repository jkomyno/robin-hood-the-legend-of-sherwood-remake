# Local browser development

Run the commands below from the repository root. The web shell fetches game
content over HTTP; `ROBINHOOD_DATA_DIR` does not select browser data.

## Convert your Full installation

Use `convert_datadir --format shipping --web-content-manifest
--web-content-edition full --audio-format opus --zstd-window-log 30`, with
`--map-format avif-q60 --interface-image-format avif-q60
--rle-sprite-format avif-q60`. The pinned encoder versions and source hashes are
in [COMPRESSION.md](../docs/COMPRESSION.md). Install AVIF tools with
`bash scripts/install_pinned_avif_tools.sh ABSENT_ABSOLUTE_DESTINATION`.
Pass the pinned opus-tools prefix through `--opus-tools-dir`.

The canonical [conversion wrapper](../scripts/build_web_shipping_datadir.sh)
also requires the optional lossless music remaster directory. When using your
installation's original music, invoke the converter directly without
`--lossless-music-dir`; it logs this choice and still verifies libopus for every
Opus encode.

On macOS, run conversion in a Linux container with the source installation
mounted read-only. The current converter verifies loaded libopus through glibc's
loader trace. On Rosetta hosts without x86-64-v3 support, build the converter
inside the container with this invocation-specific CPU override:

```sh
env -u RUSTUP_TOOLCHAIN \
  CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER=cc cargo \
  --config 'target."cfg(target_arch = \"x86_64\")".rustflags=["-C","target-cpu=x86-64"]' \
  build --locked --release -p robin_rs --bin convert_datadir --features tools
```

Run the resulting converter as your host UID/GID so exported files remain yours.
Use `--resume` when its output is an existing bind-mount directory. Keep Cargo's
normal `target/` directory inside the container's own checkout.

## Stage and build

Choose an absent output directory outside the converted installation. The helper
copies and verifies the Full manifest closure, creates the existing Full-content
binding, and prepares separate runtime and corpus directories. It does not
publish any game data or require the production Demo archive.

```sh
export ROBIN_FULL_EXPORT=/absolute/path/to/shipping-en
export ROBIN_LOCAL_ROOT=/absolute/path/to/new-local-browser
node wasm-www/scripts/prepare-local-full.mjs "$ROBIN_FULL_EXPORT" "$ROBIN_LOCAL_ROOT"
export ROBIN_LOCAL_SHORT="$(node -p 'JSON.parse(require("node:fs").readFileSync(process.env.ROBIN_LOCAL_ROOT + "/receipt.json")).short')"
export ROBIN_LOCAL_PKG="$ROBIN_LOCAL_ROOT/runtime/wasm/$ROBIN_LOCAL_SHORT"
export PATH="$HOME/.cargo/bin:$PATH"

# Install the CLI version matching Cargo.lock without replacing another CLI.
env -u RUSTUP_TOOLCHAIN cargo install wasm-bindgen-cli --version 0.2.128 \
  --locked --root "$HOME/.local/share/robin_hood/local-wasm-bindgen"
pnpm --dir wasm-www install --frozen-lockfile

# macOS: Apple Clang cannot compile zstd for wasm. Select installed LLVM.
export CC_wasm32_unknown_unknown=/opt/homebrew/opt/llvm@20/bin/clang
export AR_wasm32_unknown_unknown=/opt/homebrew/opt/llvm@20/bin/llvm-ar
export CFLAGS_wasm32_unknown_unknown='-matomics -mbulk-memory'

env -u RUSTUP_TOOLCHAIN node wasm-www/scripts/build-runtime.mjs \
  --threads --profile wasm-dev --no-opt --out-dir "$ROBIN_LOCAL_PKG" \
  --bindgen "$HOME/.local/share/robin_hood/local-wasm-bindgen/bin/wasm-bindgen"
node wasm-www/scripts/stage-engine-preload-assets.mjs assets/core-datadir "$ROBIN_LOCAL_PKG"

# Supply both compression fallbacks used by the ordinary build-selection path.
# Quality 4 keeps development packaging quick; decompressed wasm is identical.
node --input-type=module <<'JS'
import { readFile, writeFile } from 'node:fs/promises';
import { brotliCompressSync, gzipSync, constants } from 'node:zlib';
const path = `${process.env.ROBIN_LOCAL_PKG}/robin_bg.wasm`;
const bytes = await readFile(path);
await writeFile(`${path}.gz`, gzipSync(bytes), { flag: 'wx' });
await writeFile(`${path}.br`, brotliCompressSync(bytes, {
    params: { [constants.BROTLI_PARAM_QUALITY]: 4 },
}), { flag: 'wx' });
JS
```

Keep the checkout on the same commit between staging and building. To build a
new source revision, stage into a new output directory; the receipt records the
runtime commit separately from the converter's commit.
Putting rustup's Cargo first in `PATH` also prevents tool-manager shims from
reintroducing `RUSTUP_TOOLCHAIN` after it has been unset.

## Serve and verify

```sh
ROBIN_LOCAL_BINARIES_ROOT="$ROBIN_LOCAL_ROOT/serve" \
  pnpm --dir wasm-www dev --host 127.0.0.1 --port 5173 --strictPort
```

Open **http://127.0.0.1:5173/?edition=full**; append `&wasm-log=debug` only
when diagnosing, since it also draws loading-phase text. Vite sends COOP
`same-origin` and COEP `require-corp`, enabling shared-memory wasm workers. The
runtime, bootstrap data and all mission/audio companions use the same local
origin. The default URL without `edition=full` expects the separate Demo corpus.

In another terminal, with `ROBIN_LOCAL_ROOT` still set:

```sh
pnpm --dir wasm-www build:site
node wasm-www/scripts/verify-static-build.mjs wasm-www/dist
node --input-type=module <<'JS'
import { verifyDatadirCorpus } from './wasm-www/scripts/verify-datadir-corpus.mjs';
console.log(await verifyDatadirCorpus(`${process.env.ROBIN_LOCAL_ROOT}/corpus`, {
    requireCurrent: false,
}));
JS
```

The datadir verifier's default CLI audits the entire retained production Demo
corpus. Its exported verifier with `requireCurrent: false` checks this local
Full-only corpus, including every file's length/hash and the Full binding.
