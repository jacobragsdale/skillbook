#!/usr/bin/env bash
# Pack Skillbook's portable Skill Manager source and replace the Nexus zip.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO/skill-manager.json"
DEFAULT_URL="https://repo.ragsdale.dev/repository/files/sources/skillbook-latest.zip"
MAX_BYTES=$((50 * 1024 * 1024))
KEYCHAIN_SERVICE="repo.ragsdale.dev"

DRY_RUN=0
REQUIRE_VALIDATE=0
DEST_URL="$DEFAULT_URL"

usage() {
  cat <<'EOF'
Usage: publish-source.sh [--dry-run] [--require-validate] [--url URL]

Pack skill-manager.json and every component path it references, then replace
the Skillbook zip on Nexus (DELETE, then PUT — the files repo is ALLOW_ONCE).

  --dry-run             Pack and validate only. Do not upload.
  --require-validate    Fail if validate-source is not available.
  --url URL             Destination artifact URL (default: skillbook-latest.zip).

Password, first match wins: NEXUS_PASSWORD, macOS keychain item
repo.ragsdale.dev for NEXUS_USER (default admin), else curl prompts.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --require-validate) REQUIRE_VALIDATE=1 ;;
    --url)
      [[ $# -ge 2 ]] || { echo "publish-source.sh: --url needs a value" >&2; exit 2; }
      DEST_URL="$2"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "publish-source.sh: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

for required in python3 zip curl shasum; do
  command -v "$required" >/dev/null 2>&1 || {
    echo "publish-source.sh: required command is missing: $required" >&2
    exit 1
  }
done

[[ -f "$MANIFEST" ]] || {
  echo "publish-source.sh: missing $MANIFEST" >&2
  exit 1
}

python3 -c 'import json, pathlib, sys; json.load(pathlib.Path(sys.argv[1]).open(encoding="utf-8"))' "$MANIFEST" || {
  echo "publish-source.sh: skill-manager.json is not valid JSON" >&2
  exit 1
}

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/skillbook-publish.XXXXXX")"
ZIP_PATH="${STAGE}.zip"
DOWNLOADED=""
AUTH_FILE=""
cleanup() {
  rm -rf -- "$STAGE"
  rm -f -- "$ZIP_PATH"
  if [[ -n "$DOWNLOADED" ]]; then
    rm -f -- "$DOWNLOADED"
  fi
  if [[ -n "$AUTH_FILE" ]]; then
    rm -f -- "$AUTH_FILE"
  fi
}
trap cleanup EXIT HUP INT TERM

COMPONENT_PATHS=()
while IFS= read -r component_path; do
  COMPONENT_PATHS+=("$component_path")
done < <(python3 - "$MANIFEST" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
paths: set[str] = set()
packages = manifest.get("packages")
if not isinstance(packages, list):
    raise SystemExit("skill-manager.json packages must be a list")
for package in packages:
    if not isinstance(package, dict):
        continue
    components = package.get("components")
    if not isinstance(components, list):
        continue
    for component in components:
        if not isinstance(component, dict):
            continue
        path = component.get("path")
        if isinstance(path, str) and path.strip():
            paths.add(path)
if not paths:
    raise SystemExit("skill-manager.json declares no component paths")
print("\n".join(sorted(paths)))
PY
)

copy_portable_path() {
  local rel="$1"
  local src="$REPO/$rel"
  local dest="$STAGE/$rel"

  if [[ -L "$src" ]]; then
    echo "publish-source.sh: refusing to pack symlink: $rel" >&2
    return 1
  fi
  if [[ -f "$src" ]]; then
    mkdir -p -- "$(dirname -- "$dest")"
    cp -- "$src" "$dest"
    return 0
  fi
  if [[ ! -d "$src" ]]; then
    echo "publish-source.sh: missing component path: $rel" >&2
    return 1
  fi

  mkdir -p -- "$dest"
  while IFS= read -r -d '' item; do
    local child="${item#"$src"/}"
    if [[ "$child" == "$item" ]]; then
      echo "publish-source.sh: path is not under $rel: $item" >&2
      return 1
    fi
    if [[ -L "$item" ]]; then
      echo "publish-source.sh: refusing to pack symlink: $rel/$child" >&2
      return 1
    fi
    if [[ -d "$item" ]]; then
      mkdir -p -- "$dest/$child"
    elif [[ -f "$item" ]]; then
      mkdir -p -- "$(dirname -- "$dest/$child")"
      cp -- "$item" "$dest/$child"
    else
      echo "publish-source.sh: refusing special file: $rel/$child" >&2
      return 1
    fi
  done < <(
    find "$src" \
      \( -name '__pycache__' -o -name '.DS_Store' -o -name '*.pyc' \
      -o -name '.ruff_cache' -o -name '.pytest_cache' -o -name '.git' \) -prune -o \
      -mindepth 1 -print0
  )
}

cp -- "$MANIFEST" "$STAGE/skill-manager.json"
for rel in "${COMPONENT_PATHS[@]}"; do
  case "$rel" in
    /* | .. | ../* | */.. | */../*)
      echo "publish-source.sh: component path escapes the repository: $rel" >&2
      exit 1
      ;;
  esac
  copy_portable_path "$rel"
done

(
  cd "$STAGE"
  zip -r -X -q "$ZIP_PATH" .
)

[[ -f "$STAGE/skill-manager.json" ]] || {
  echo "publish-source.sh: staged tree is missing skill-manager.json" >&2
  exit 1
}

ZIP_SIZE="$(wc -c <"$ZIP_PATH" | tr -d ' ')"
if [[ "$ZIP_SIZE" -le 0 ]]; then
  echo "publish-source.sh: produced an empty zip" >&2
  exit 1
fi
if [[ "$ZIP_SIZE" -gt "$MAX_BYTES" ]]; then
  echo "publish-source.sh: zip is ${ZIP_SIZE} bytes; Skill Manager limit is ${MAX_BYTES}" >&2
  exit 1
fi

CHECKSUM="$(shasum -a 256 "$ZIP_PATH" | awk '{print $1}')"

find_validate_source() {
  if command -v validate-source >/dev/null 2>&1; then
    command -v validate-source
    return 0
  fi
  local sibling
  sibling="$(cd "$REPO/.." && pwd)/skill-manager/src-tauri/target"
  local candidate
  for candidate in "$sibling/release/validate-source" "$sibling/debug/validate-source"; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

VALIDATE_BIN=""
if VALIDATE_BIN="$(find_validate_source)"; then
  "$VALIDATE_BIN" "$STAGE"
else
  if [[ "$REQUIRE_VALIDATE" -eq 1 ]]; then
    echo "publish-source.sh: validate-source was required but not found" >&2
    exit 1
  fi
  echo "publish-source.sh: validate-source not found; packed zip was not validated" >&2
fi

echo "packed ${ZIP_SIZE} bytes  sha256=${CHECKSUM}"
unzip -Z1 "$ZIP_PATH" | sort

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "dry-run: not uploading ${DEST_URL}"
  exit 0
fi

NEXUS_USER="${NEXUS_USER:-admin}"
PASSWORD="${NEXUS_PASSWORD:-}"
if [[ -z "$PASSWORD" ]] && command -v security >/dev/null 2>&1; then
  PASSWORD="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -a "$NEXUS_USER" -w 2>/dev/null || true)"
fi

AUTH_ARGS=()
if [[ -n "$PASSWORD" ]]; then
  AUTH_FILE="$(mktemp "${TMPDIR:-/tmp}/skillbook-nexus-auth.XXXXXX")"
  chmod 600 "$AUTH_FILE"
  python3 - "$AUTH_FILE" "$NEXUS_USER" "$PASSWORD" <<'PY'
from pathlib import Path
import sys

path, user, password = sys.argv[1], sys.argv[2], sys.argv[3]
# curl --config user values treat backslash and quote as syntax.
if any(ch in user or ch in password for ch in '"\\\n\r'):
    raise SystemExit("Nexus credentials contain characters curl --config cannot quote")
Path(path).write_text(f'user = "{user}:{password}"\n', encoding="utf-8")
PY
  unset PASSWORD
  AUTH_ARGS=(--config "$AUTH_FILE")
else
  AUTH_ARGS=(--user "$NEXUS_USER")
fi

delete_status="$(
  curl "${AUTH_ARGS[@]}" -sS -o /dev/null -w '%{http_code}' \
    --connect-timeout 10 --max-time 60 \
    -X DELETE "$DEST_URL"
)"
case "$delete_status" in
  200 | 204 | 404) ;;
  *)
    echo "publish-source.sh: DELETE ${DEST_URL} failed with HTTP ${delete_status}" >&2
    exit 1
    ;;
esac

upload_status="$(
  curl "${AUTH_ARGS[@]}" -sS -o /dev/null -w '%{http_code}' \
    --connect-timeout 10 --max-time 120 \
    --upload-file "$ZIP_PATH" "$DEST_URL"
)"
if [[ "$upload_status" != 201 ]]; then
  echo "publish-source.sh: upload ${DEST_URL} failed with HTTP ${upload_status}" >&2
  exit 1
fi

DOWNLOADED="$(mktemp "${TMPDIR:-/tmp}/skillbook-downloaded.XXXXXX.zip")"
curl -fsS --connect-timeout 10 --max-time 120 -o "$DOWNLOADED" "$DEST_URL"
REMOTE_CHECKSUM="$(shasum -a 256 "$DOWNLOADED" | awk '{print $1}')"
if [[ "$REMOTE_CHECKSUM" != "$CHECKSUM" ]]; then
  echo "publish-source.sh: uploaded zip sha256 ${REMOTE_CHECKSUM} does not match local ${CHECKSUM}" >&2
  exit 1
fi

echo "published ${DEST_URL}"
echo "sha256 ${CHECKSUM}"
echo "Refresh Skillbook in Skill Manager, then Update installed packages."
