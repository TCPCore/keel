#!/usr/bin/env bash
# Run one Muse Code task headlessly, from a brief file in muse/.
#
#   scripts/muse_run.sh muse/01-models.md
#   scripts/muse_run.sh --smoke
#
# The key is read from .env (MODEL_API_KEY or META_API_KEY) and piped over
# stdin, so it never appears in argv or in shell history. Nothing is committed;
# the audit gate still decides what leaves this machine.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MUSE="$ROOT/.tools/bin/muse"
[[ -x "$MUSE" ]] || {
    echo "muse not installed. Run: bash .tools/meta-install.sh (see muse/README.md)" >&2
    exit 2
}

if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

KEY="${MODEL_API_KEY:-${META_API_KEY:-}}"
if [[ -z "$KEY" ]]; then
    echo "no key: put MODEL_API_KEY=... in .env (gitignored) and re-run" >&2
    exit 2
fi

export META_API_KEY="$KEY"
export XDG_CONFIG_HOME="$ROOT/.tools/config"
export MUSE_AUTH_PATH="$ROOT/.tools/muse-auth.json"

MODEL="${MUSE_MODEL:-muse-spark-1.3}"
EFFORT="${MUSE_EFFORT:-high}"

run() {
    local label="$1" prompt_file="$2"
    local out="$ROOT/.tools/runs/$label"
    mkdir -p "$out"
    echo "muse: $label ($MODEL, effort=$EFFORT)" >&2
    printf '%s' "$KEY" | "$MUSE" exec \
        --api-key-stdin \
        --provider meta \
        --model "$MODEL" \
        --reasoning-effort "$EFFORT" \
        --workspace "$ROOT" \
        --json \
        --prompt-file "$prompt_file" \
        | tee "$out/events.jsonl"
    echo "saved $out/events.jsonl" >&2
}

if [[ "${1:-}" == "--smoke" ]]; then
    tmp="$(mktemp)"
    printf 'Reply with exactly: keel ok\n' >"$tmp"
    run "smoke" "$tmp"
    rm -f "$tmp"
    exit 0
fi

BRIEF="${1:?usage: scripts/muse_run.sh muse/NN-name.md | --smoke}"
[[ -f "$BRIEF" ]] || {
    echo "no such brief: $BRIEF" >&2
    exit 2
}
run "$(basename "${BRIEF%.md}")" "$BRIEF"
