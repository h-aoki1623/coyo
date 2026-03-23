#!/usr/bin/env node
/**
 * PostToolUse Hook: Auto-format Python files with black after edits
 *
 * Cross-platform (Windows, macOS, Linux)
 *
 * Runs after Edit tool use. If the edited file is a .py file,
 * formats it with black. Fails silently if black isn't installed.
 */

const { execFileSync } = require("child_process");
const path = require("path");

const MAX_STDIN = 1024 * 1024; // 1MB limit
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
    const filePath = input.tool_input?.file_path;

    if (filePath && /\.py$/.test(filePath)) {
      try {
        execFileSync("black", ["--quiet", filePath], {
          cwd: path.dirname(path.resolve(filePath)),
          stdio: ["pipe", "pipe", "pipe"],
          timeout: 15000,
        });
      } catch {
        // black not installed, file missing, or failed — non-blocking
      }
    }
  } catch {
    // Invalid input — pass through
  }

  process.stdout.write(data);
  process.exit(0);
});
