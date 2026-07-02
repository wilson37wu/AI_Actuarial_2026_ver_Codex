#!/usr/bin/env bash
# cowork_sync_push.sh — Push local model updates to GitHub main from a Claude Cowork sandbox.
#
# Implements the AGENT_COORDINATION.md mandate: NEVER run git write operations
# against the virtiofs-mounted .git (ghost-lock hazard). All git work happens
# in a throwaway clone in /tmp; changed files are copied in from the mount.
#
# Usage:
#   bash scripts/cowork_sync_push.sh "<commit message>" [file ...]
#   - With file args: only those paths (relative to repo root) are synced.
#   - Without file args: all tracked files that differ (content-level, CRLF-insensitive)
#     between mount and origin/main are synced.
#
# Auth: reads a GitHub PAT from <repo>/.git/gh_token (never tracked by git).
#
# Exit codes: 0 = pushed (or nothing to push), 1 = config/auth error, 2 = lock held by other agent.

set -euo pipefail

MOUNT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOKEN_FILE="$MOUNT_DIR/.git/gh_token"
COMMIT_MSG="${1:?usage: cowork_sync_push.sh \"<commit message>\" [file ...]}"
shift || true

[ -f "$TOKEN_FILE" ] || { echo "ERROR: token file missing: $TOKEN_FILE" >&2; exit 1; }
TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
REMOTE_URL="$(git -C "$MOUNT_DIR" remote get-url origin | sed -E "s#https://(x-access-token@)?#https://x-access-token:${TOKEN}@#")"

CLONE_DIR="$(mktemp -d /tmp/cycle_clone.XXXXXX)"
trap 'rm -rf "$CLONE_DIR"' EXIT
git clone --depth 50 "$REMOTE_URL" "$CLONE_DIR" >/dev/null 2>&1
git -C "$CLONE_DIR" config user.name  "${GIT_AUTHOR_NAME:-claude-cowork-agent}"
git -C "$CLONE_DIR" config user.email "${GIT_AUTHOR_EMAIL:-claude-agent@actuarial-bot.local}"

# --- Lock protocol (AGENT_COORDINATION.md §2): preflight + acquire ---
if [ -f "$CLONE_DIR/scripts/agent_lock.py" ]; then
  ( cd "$CLONE_DIR" && python3 scripts/agent_lock.py preflight --owner claude ) \
    || { echo "YIELD: lock held by another agent" >&2; exit 2; }
  ( cd "$CLONE_DIR" && python3 scripts/agent_lock.py acquire --owner claude --task "cowork sync push" ) \
    || { echo "YIELD: lost lock race" >&2; exit 2; }
fi

# --- Determine files to sync ---
if [ "$#" -gt 0 ]; then
  FILES=("$@")
else
  mapfile -t FILES < <(
    cd "$CLONE_DIR" && git ls-files | while read -r f; do
      if [ -f "$MOUNT_DIR/$f" ] && ! diff -q --strip-trailing-cr "$MOUNT_DIR/$f" "$CLONE_DIR/$f" >/dev/null 2>&1; then
        echo "$f"
      fi
    done
  )
fi

SYNCED=0
for f in "${FILES[@]:-}"; do
  [ -z "$f" ] && continue
  case "$f" in
    .agent_lock.json|.git/*|*.tmp|*__pycache__*) continue ;;
  esac
  mkdir -p "$CLONE_DIR/$(dirname "$f")"
  cp "$MOUNT_DIR/$f" "$CLONE_DIR/$f"
  git -C "$CLONE_DIR" add -- "$f"
  SYNCED=$((SYNCED+1))
done

if git -C "$CLONE_DIR" diff --cached --quiet; then
  echo "Nothing to push (0 content-level differences)."
else
  git -C "$CLONE_DIR" commit -m "$COMMIT_MSG" >/dev/null
  for i in 1 2 3; do
    git -C "$CLONE_DIR" fetch origin && git -C "$CLONE_DIR" rebase origin/main >/dev/null 2>&1 || true
    if git -C "$CLONE_DIR" push origin HEAD:main; then break; fi
    [ "$i" = 3 ] && { echo "ERROR: push rejected 3x" >&2; exit 1; }
    sleep 3
  done
  echo "Pushed $SYNCED file(s) to origin/main."
fi

# --- Release lock ---
if [ -f "$CLONE_DIR/scripts/agent_lock.py" ]; then
  ( cd "$CLONE_DIR" && python3 scripts/agent_lock.py release --owner claude ) || true
fi
