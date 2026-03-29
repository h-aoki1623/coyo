#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
command="$(jq -r '.tool_input.command // empty' <<< "$input" 2>/dev/null)" || exit 0

if [[ "$command" =~ git[[:space:]]+commit ]]; then
  msg="[Hook] Pre-Commit Checklist — have you completed ALL of these?
  1. Tests written for new/changed code
  2. Tests passing (pytest / npx jest)
  3. Build passing (tsc --noEmit / expo export)
  4. Coverage >= 80% for new/changed code
If NOT, abort this commit and run tests first.
If the user explicitly asked to skip testing, proceed."

  jq -Rn --arg msg "$msg" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: $msg
    }
  }'
fi

exit 0
