#!/usr/bin/env bash
# .claude/hooks/check-uv-install.sh — PreToolUse Bash hook (speed bump).
#
# WHAT THIS IS
#   A "speed bump" that catches accidental, plain-text invocations of uv/pip
#   commands which would bypass the supply-chain release-age cooldown enforced
#   by apps/api/uv.lock and apps/mobile/.npmrc.
#
# WHAT THIS IS NOT
#   A security boundary against a motivated or compromised actor. Regex on a
#   shell command string cannot reliably understand variable expansion,
#   string concatenation, eval, $(), backticks, heredocs, PATH shadowing,
#   indirect interpreters, or "rewrite the hook config in settings.json".
#   Real supply-chain enforcement lives in:
#     - apps/api/uv.lock + uv sync --frozen everywhere (PR1a/1b)
#     - apps/mobile/.npmrc min-release-age + engine-strict (PR1b)
#     - CI hash-pin on the wrappers and these hook scripts (PR2)
#     - Code review on .claude/settings.json changes
#
# Sanctioned entry points (the hook lets these through):
#     make api-lock                  → regenerate uv.lock with the cooldown
#     make api-install               → uv sync --frozen --extra dev
#     bash scripts/uv-install.sh ... → wrapper that injects --exclude-newer
#     bash scripts/install-npm-pinned.sh
#     uv sync --frozen ...           → restore from the lockfile
#     uv venv / uv run / uv --version → no resolution, no cooldown needed
#
# What the hook blocks (each is a "common accident" Claude might emit):
#     uv pip install / uv pip compile / uv pip sync / uv pip uninstall
#     uv add / uv lock
#     uv sync (without --frozen)
#     uv tool install / uv tool run / uvx
#     pip install (pip, pip3, python -m pip, python3 -m pip)
#     bash -c / sh -c / eval / python -c   when the inner string mentions
#       any of the above
#     chmod / rm / mv / cp / sed -i / tee / ln / output redirection (>, >>)
#       targeting any file in the protected list (so the hook cannot be
#       silently disabled by `chmod -x`-ing it from Bash)
#
# Known limitations (intentionally not chased — see "What this is not"):
#     - Variable expansion: `U=uv; $U pip install evil` is NOT caught
#     - String concatenation: `"u""v" pip install evil` is NOT caught
#     - Indirect via PATH-shadowing or aliases is NOT caught
#     - Editing .claude/settings.json to remove the hook is NOT caught
#       (this was an explicit project decision to keep settings.json editable)
#
# To legitimately edit a protected file or run an off-list uv command for
# a one-off task, see docs/CONTRIB.md "Supply-chain defense" for the
# session-disable procedure.

set -euo pipefail

# -----------------------------------------------------------------------------
# Fail-CLOSED on any error: if jq is missing, the JSON is malformed, or any
# preflight check fails, refuse the tool call rather than falling through.
# A silent fail-open here would defeat the entire purpose of the hook.
# -----------------------------------------------------------------------------

if ! command -v jq >/dev/null 2>&1; then
  echo "BLOCKED by .claude/hooks/check-uv-install.sh:" >&2
  echo "  jq is not installed; the supply-chain hook cannot inspect the command." >&2
  echo "  Install jq (brew install jq / apt install jq) or disable the hook." >&2
  exit 2
fi

input="$(cat)"
command="$(jq -r '.tool_input.command // empty' <<< "$input" 2>/dev/null || true)"
[[ -z "$command" ]] && exit 0  # not a Bash invocation

block() {
  cat >&2 <<EOF
BLOCKED by .claude/hooks/check-uv-install.sh (supply-chain speed bump):
  $1

This command would bypass the release-age cooldown that PR1a/1b baked
into apps/api/uv.lock and apps/mobile/.npmrc. Use one of the sanctioned
entry points instead:

  make api-lock         # regenerate uv.lock with the 7-day cooldown
  make api-install      # uv sync --frozen from the lockfile

For one-off legitimate cases that can't go through these paths, see
docs/CONTRIB.md "Supply-chain defense" for the session-disable procedure.
EOF
  exit 2
}

# -----------------------------------------------------------------------------
# Pattern set 1: forbidden uv subcommands (token sequence anywhere in the
# command, including chained commands like `cd foo && uv pip install bar`).
#
# The lead-in character class includes whitespace, common shell separators,
# `(` for $() / process substitution, and backtick for `…` substitution.
# -----------------------------------------------------------------------------

LEAD='(^|[[:space:]\;\&\|\(\`])'

# uv pip install / compile / sync / uninstall — direct Python deps install.
if [[ "$command" =~ ${LEAD}uv[[:space:]]+pip[[:space:]]+(install|compile|sync|uninstall) ]]; then
  block "uv pip ${BASH_REMATCH[2]} detected"
fi

# uv add — adds a dep without --exclude-newer.
if [[ "$command" =~ ${LEAD}uv[[:space:]]+add([[:space:]]|$) ]]; then
  block "uv add detected"
fi

# uv remove — removes a dep AND triggers a re-resolve, same risk as add.
if [[ "$command" =~ ${LEAD}uv[[:space:]]+remove([[:space:]]|$) ]]; then
  block "uv remove detected (use scripts/uv-install.sh remove via make api-lock)"
fi

# uv lock — regenerating the lockfile must go through scripts/uv-install.sh
# (which is invoked as `bash scripts/uv-install.sh lock`, never `uv lock`).
if [[ "$command" =~ ${LEAD}uv[[:space:]]+lock([[:space:]]|$) ]]; then
  block "uv lock detected (use 'make api-lock' instead)"
fi

# uv tool install / uv tool run — moral equivalent of `pip install --user`,
# downloads from PyPI with no cooldown.
if [[ "$command" =~ ${LEAD}uv[[:space:]]+tool[[:space:]]+(install|run|upgrade) ]]; then
  block "uv tool ${BASH_REMATCH[2]} detected"
fi

# uvx — ephemeral tool execution; downloads from PyPI on first use.
if [[ "$command" =~ ${LEAD}uvx([[:space:]]|$) ]]; then
  block "uvx detected (downloads tools without the cooldown)"
fi

# uv sync (without --frozen). We extract the segment from `uv sync` to the
# next shell separator, strip any line comment, then look for `--frozen` as
# a STANDALONE TOKEN (so `--frozen-mode` doesn't accidentally allow it).
if [[ "$command" =~ uv[[:space:]]+sync[^\&\|\;]* ]]; then
  uv_sync_segment="${BASH_REMATCH[0]}"
  # Strip a `# comment` tail if present (defends against `uv sync # --frozen`).
  uv_sync_segment_clean="${uv_sync_segment%%#*}"
  if ! [[ "$uv_sync_segment_clean" =~ (^|[[:space:]])--frozen([[:space:]=]|$) ]]; then
    block "uv sync without --frozen detected"
  fi
fi

# pip install in any of its forms.
if [[ "$command" =~ ${LEAD}(python[23]?[[:space:]]+-m[[:space:]]+)?pip[23]?[[:space:]]+install ]]; then
  block "pip install detected"
fi

# -----------------------------------------------------------------------------
# Pattern set 2: indirect-execution wrappers that contain a forbidden inner
# command. We do not try to chase variable expansion or alias indirection;
# we only catch the direct, plain-text "bash -c '... uv pip install ...'"
# class of accidents (per the project's "speed bump" positioning).
# -----------------------------------------------------------------------------

# bash -c / sh -c with uv/pip inside the quoted string.
# (\b word boundaries are not reliable in bash POSIX ERE on macOS, so we
# rely on greedy `.*` + the explicit token shapes in the alternation.)
if [[ "$command" =~ (bash|sh)[[:space:]]+-c[[:space:]]+[\"\'].*(uv[[:space:]]+(pip|add|lock|sync|tool)|uvx|pip[23]?[[:space:]]+install) ]]; then
  block "indirect uv/pip via ${BASH_REMATCH[1]} -c detected"
fi

# eval with uv/pip inside the quoted string.
if [[ "$command" =~ eval[[:space:]]+[\"\'].*(uv[[:space:]]+(pip|add|lock|sync|tool)|uvx|pip[23]?[[:space:]]+install) ]]; then
  block "indirect uv/pip via eval detected"
fi

# python -c with pip / subprocess in the inline script.
if [[ "$command" =~ python[23]?[[:space:]]+-c[[:space:]]+[\"\'].*(pip|subprocess|os\.exec|__import__) ]]; then
  block "python -c with pip/subprocess detected"
fi

# -----------------------------------------------------------------------------
# Pattern set 3: file mutation against any protected file. The Edit hook
# only sees Edit/Write/MultiEdit; bare `rm`, `chmod -x`, `sed -i` etc. would
# otherwise let an actor disable the wrappers or hooks themselves from Bash.
# -----------------------------------------------------------------------------

PROTECTED='(apps/mobile/\.npmrc|scripts/uv-install\.sh|scripts/install-npm-pinned\.sh|\.claude/hooks/check-uv-install\.sh|\.claude/hooks/check-protected-files\.sh)'

# chmod / rm / mv / cp / tee / truncate <flags...> <protected-path>
if [[ "$command" =~ (^|[[:space:]\;\&\|\(\`])(chmod|rm|mv|cp|tee|truncate)[[:space:]][^\&\|\;]*${PROTECTED} ]]; then
  block "${BASH_REMATCH[2]} targeting protected file detected"
fi

# sed -i (in-place edit)
if [[ "$command" =~ sed[[:space:]]+(-i|--in-place)[^\&\|\;]*${PROTECTED} ]]; then
  block "sed -i targeting protected file detected"
fi

# ln (creating a symlink at, or to, a protected path — both directions risky)
if [[ "$command" =~ (^|[[:space:]\;\&\|\(\`])ln[[:space:]][^\&\|\;]*${PROTECTED} ]]; then
  block "ln targeting protected file detected"
fi

# Output redirection: > or >> targeting a protected path.
if [[ "$command" =~ \>+[[:space:]]*[^\&\|\;]*${PROTECTED} ]]; then
  block "output redirection to protected file detected"
fi

exit 0
