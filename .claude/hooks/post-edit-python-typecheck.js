#!/usr/bin/env node
/**
 * PostToolUse Hook: mypy type check after editing .py files
 *
 * Cross-platform (Windows, macOS, Linux)
 *
 * Runs after Edit tool use on Python files. Walks up from the file's
 * directory to find the nearest pyproject.toml, setup.cfg, or mypy.ini,
 * then runs mypy and reports only errors related to the edited file.
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

const MYPY_CONFIG_FILES = ["mypy.ini", ".mypy.ini", "pyproject.toml", "setup.cfg"];

function findProjectRoot(startDir) {
  let dir = startDir;
  const root = path.parse(dir).root;
  let depth = 0;

  while (dir !== root && depth < 20) {
    for (const configFile of MYPY_CONFIG_FILES) {
      if (fs.existsSync(path.join(dir, configFile))) {
        return dir;
      }
    }
    dir = path.dirname(dir);
    depth++;
  }

  return null;
}

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

      const projectRoot = findProjectRoot(path.dirname(resolvedPath));
      const cwd = projectRoot || path.dirname(resolvedPath);

      try {
        execFileSync(
          "mypy",
          ["--no-error-summary", "--no-pretty", resolvedPath],
          {
            cwd,
            encoding: "utf8",
            stdio: ["pipe", "pipe", "pipe"],
            timeout: 30000,
          },
        );
      } catch (err) {
        // mypy exits non-zero when there are errors
        const output = (err.stdout || "") + (err.stderr || "");
        const relPath = path.relative(cwd, resolvedPath);
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
            "[Hook] mypy errors in " + path.basename(filePath) + ":",
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
