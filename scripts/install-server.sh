#!/usr/bin/env bash
# Symlink each voice-skills/<name> into ~/.codex/skills, where codex (both
# jarvis brains run on it) discovers skills. Runs ON THE SERVER against the
# clone at ~/jarvis-skills; `make deploy` invokes it after every pull.
# Prunes stale links that point into the clone, leaves everything else alone.
set -euo pipefail

CLONE="$HOME/jarvis-skills"
SRC="$CLONE/voice-skills"
DEST="$HOME/.codex/skills"

mkdir -p "$DEST"

# Prune links into the clone whose source is gone (renamed/removed skills).
for link in "$DEST"/*; do
    [ -L "$link" ] || continue
    target=$(readlink "$link")
    case "$target" in
        "$CLONE"/*) [ -e "$target" ] || { rm "$link"; echo "pruned    $link"; } ;;
    esac
done

for skill in "$SRC"/*/; do
    [ -f "$skill/SKILL.md" ] || continue
    name=$(basename "$skill")
    ln -sfn "${skill%/}" "$DEST/$name"
    echo "linked    $DEST/$name"
done
