#!/usr/bin/env node
/**
 * PostToolUse Hook: Lint Python files with ruff after edits
 *
 * Cross-platform (Windows, macOS, Linux)
 *
 * Runs after Edit tool use on Python files. Applies auto-fixes with
 * ruff check --fix, then reports any remaining errors for the edited file.
 */

const { execFileSync } = require("child_process");
const fs = require("fs");
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
      const resolvedPath = path.resolve(filePath);
      if (!fs.existsSync(resolvedPath)) {
        process.stdout.write(data);
        process.exit(0);
      }

      try {
        // Auto-fix what ruff can fix
        execFileSync("ruff", ["check", "--fix", "--quiet", resolvedPath], {
          cwd: path.dirname(resolvedPath),
          stdio: ["pipe", "pipe", "pipe"],
          timeout: 15000,
        });
      } catch {
        // --fix exits non-zero if unfixable errors remain — that's expected
      }

      try {
        // Report remaining errors
        execFileSync("ruff", ["check", "--no-fix", resolvedPath], {
          cwd: path.dirname(resolvedPath),
          encoding: "utf8",
          stdio: ["pipe", "pipe", "pipe"],
          timeout: 15000,
        });
      } catch (err) {
        const output = (err.stdout || "") + (err.stderr || "");
        const relPath = path.relative(
          path.dirname(resolvedPath),
          resolvedPath,
        );
        const candidates = new Set([filePath, resolvedPath, relPath]);
        const relevantLines = output
          .split("\n")
          .filter((line) => {
            for (const candidate of candidates) {
              if (line.includes(candidate)) return true;
            }
            return false;
          })
          .slice(0, 10);

        if (relevantLines.length > 0) {
          console.error(
            "[Hook] ruff errors in " + path.basename(filePath) + ":",
          );
          relevantLines.forEach((line) => console.error(line));
        }
      }
    }
  } catch {
    // Invalid input — pass through
  }

  process.stdout.write(data);
  process.exit(0);
});
