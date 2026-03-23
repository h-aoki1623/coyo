#!/usr/bin/env node
/**
 * PostToolUse Hook: Lint JS/TS files with ESLint after edits
 *
 * Cross-platform (Windows, macOS, Linux)
 *
 * Runs after Edit tool use on JS/TS files. Walks up from the file's
 * directory to find the nearest ESLint config, applies auto-fixes,
 * then reports any remaining errors for the edited file.
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

const ESLINT_CONFIG_FILES = [
  "eslint.config.js",
  "eslint.config.mjs",
  "eslint.config.cjs",
  "eslint.config.ts",
  "eslint.config.mts",
  "eslint.config.cts",
  ".eslintrc.js",
  ".eslintrc.cjs",
  ".eslintrc.json",
  ".eslintrc.yml",
  ".eslintrc.yaml",
  ".eslintrc",
];

function findProjectRoot(startDir) {
  let dir = startDir;
  const root = path.parse(dir).root;
  let depth = 0;

  while (dir !== root && depth < 20) {
    for (const configFile of ESLINT_CONFIG_FILES) {
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

    if (filePath && /\.(ts|tsx|js|jsx)$/.test(filePath)) {
      const resolvedPath = path.resolve(filePath);
      if (!fs.existsSync(resolvedPath)) {
        process.stdout.write(data);
        process.exit(0);
      }

      const projectRoot = findProjectRoot(path.dirname(resolvedPath));
      if (!projectRoot) {
        // No ESLint config found — skip
        process.stdout.write(data);
        process.exit(0);
      }

      const npxBin = process.platform === "win32" ? "npx.cmd" : "npx";

      // Auto-fix then report remaining errors
      try {
        execFileSync(npxBin, ["eslint", "--fix", "--quiet", resolvedPath], {
          cwd: projectRoot,
          stdio: ["pipe", "pipe", "pipe"],
          timeout: 30000,
        });
      } catch {
        // --fix exits non-zero if unfixable errors remain — that's expected
      }

      try {
        execFileSync(
          npxBin,
          ["eslint", "--no-fix", "--format", "unix", resolvedPath],
          {
            cwd: projectRoot,
            encoding: "utf8",
            stdio: ["pipe", "pipe", "pipe"],
            timeout: 30000,
          },
        );
      } catch (err) {
        const output = (err.stdout || "") + (err.stderr || "");
        const relPath = path.relative(projectRoot, resolvedPath);
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
            "[Hook] ESLint errors in " + path.basename(filePath) + ":",
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
