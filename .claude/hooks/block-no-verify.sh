#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
command="$(jq -r '.tool_input.command // empty' <<< "$input" 2>/dev/null)" || exit 0

if [[ "$command" =~ git[[:space:]]+commit ]] && [[ "$command" =~ --no-verify|-n[[:space:]] ]]; then
  echo "BLOCKED: git commit --no-verify is prohibited. Pre-commit hooks must always run. Fix the underlying issue instead of bypassing hooks." >&2
  exit 2
fi

exit 0
