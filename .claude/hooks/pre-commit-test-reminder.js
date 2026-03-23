#!/usr/bin/env node
/**
 * PreToolUse Hook: Remind Claude to run tests before committing
 *
 * Fires when a Bash tool call contains "git commit". Outputs a
 * reminder on stderr (visible to Claude as hook feedback) but
 * does NOT block the commit — the reminder is a soft gate.
 */

const MAX_STDIN = 1024 * 1024;
let data = "";
process.stdin.setEncoding("utf8");

process.stdin.on("data", (chunk) => {
  if (data.length < MAX_STDIN) {
    data += chunk;
  }
});

process.stdin.on("end", () => {
  try {
    const input = JSON.parse(data);
    const command = input.tool_input?.command || "";

    if (/git\s+commit/.test(command)) {
      console.error(
        [
          "[Hook] ⚠️ Pre-Commit Checklist — have you completed ALL of these?",
          "  1. Tests written for new/changed code",
          "  2. Tests passing (pytest / npx jest)",
          "  3. Build passing (tsc --noEmit / expo export)",
          "  4. Coverage ≥ 80% for new/changed code",
          "If NOT, abort this commit and run tests first.",
          "If the user explicitly asked to skip testing, proceed.",
        ].join("\n"),
      );
    }
  } catch {
    // Invalid input — pass through
  }

  process.stdout.write(data);
  process.exit(0);
});
