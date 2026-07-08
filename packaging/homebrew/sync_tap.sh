#!/usr/bin/env bash
# sync_tap.sh — local dry-run helper for regenerating the Homebrew formula.
# Run from the repository root:
#   ./packaging/homebrew/sync_tap.sh --version 0.3.0 --dry-run
#   ./packaging/homebrew/sync_tap.sh --version 0.3.0 --push

set -euo pipefail

VERSION=""
DRY_RUN=false
PUSH=false
OUTPUT=""

usage() {
    cat <<EOF
Usage: $0 --version X.Y.Z [--dry-run] [--push] [--output FILE]

Options:
  --version X.Y.Z   Package version to generate formula for (required)
  --dry-run          Show generated formula to stdout (default)
  --push             Commit and push to homebrew-tap (requires HOMEBREW_TAP_TOKEN)
  --output FILE      Write formula to FILE instead of stdout
  --help             Show this message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)
            VERSION="$2"; shift 2 ;;
        --dry-run)
            DRY_RUN=true; PUSH=false; shift ;;
        --push)
            DRY_RUN=false; PUSH=true; shift ;;
        --output)
            OUTPUT="$2"; shift 2 ;;
        --help)
            usage; exit 0 ;;
        *)
            echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

if [[ -z "$VERSION" ]]; then
    echo "ERROR: --version is required" >&2
    usage >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENERATE="$SCRIPT_DIR/generate_formula.py"

if [[ ! -f "$GENERATE" ]]; then
    echo "ERROR: generate_formula.py not found at $GENERATE" >&2
    exit 1
fi

# Build command
CMD="python3 '$GENERATE' --version '$VERSION'"
if [[ -n "$OUTPUT" ]]; then
    CMD="$CMD --output '$OUTPUT'"
fi
if [[ "$DRY_RUN" == true ]]; then
    CMD="$CMD --dry-run"
fi

echo "==> Running: $CMD"
eval "$CMD"

# Push if requested
if [[ "$PUSH" == true ]]; then
    if [[ -z "${HOMEBREW_TAP_TOKEN:-}" ]]; then
        echo "ERROR: HOMEBREW_TAP_TOKEN env var is not set." >&2
        echo "Set it with: export HOMEBREW_TAP_TOKEN=ghp_..." >&2
        exit 1
    fi

    TAP_DIR="$(mktemp -d)"
    git clone "https://x-access-token:${HOMEBREW_TAP_TOKEN}@github.com/Yogi776/homebrew-tap.git" "$TAP_DIR"
    cd "$TAP_DIR"

    FORMULA_FILE="$TAP_DIR/Formula/ai-data-platform.rb"
    python3 "$GENERATE" --version "$VERSION" --output "$FORMULA_FILE"

    git add Formula/ai-data-platform.rb
    git commit -m "ai-data-platform $VERSION"
    git push origin main

    echo "==> Pushed formula for $VERSION to homebrew-tap"
    rm -rf "$TAP_DIR"
fi
