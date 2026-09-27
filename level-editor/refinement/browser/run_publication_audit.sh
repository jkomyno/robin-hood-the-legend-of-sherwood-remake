#!/bin/bash
# Run the publication browser audit with its own editor dev server, e.g. inside a sandbox:
#   level-editor/refinement/browser/run_publication_audit.sh <config.json> [port]
# The server runs in its own process group (stopped by group, never pkill), without HMR or
# file watching; the Chromium profile lives under TMPDIR (see verify_publication.mjs).
set -u
config=$(realpath "$1"); port=${2:-5181}
here=$(dirname "$(realpath "$0")")
cd "$here/../../app"
AUDIT_PORT=$port setsid npx vite --config "$here/vite.audit.config.mts" > "$(dirname "$config")/devserver-$port.log" 2>&1 &
group=$!
trap 'kill -TERM -- -$group 2>/dev/null; wait $group 2>/dev/null' EXIT
ready=; for _ in $(seq 1 120); do curl -s -o /dev/null "http://127.0.0.1:$port/" && { ready=1; break; }; sleep 1; done
[ -n "$ready" ] || { echo "Audit dev server did not start; see devserver-$port.log" >&2; exit 1; }
node "$here/verify_publication.mjs" "$config" "http://127.0.0.1:$port"
