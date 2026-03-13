# Git

### Branching Rules (MUST)

- **Before making any file modifications or creating new files**, Claude MUST check the current git branch.
- If the current git branch is `main` or `develop`, Claude MUST:
  1. Create a new worktree with a new branch using git commands.
     The worktree directory name MUST replace `/` in the branch name with `-` to keep a flat directory structure:
     ```bash
     # Branch: feat/add-login → Directory: feat-add-login
     git worktree add .claude/worktrees/<dir-name> -b <branch-name>
     ```
  2. Move into the worktree directory:
     ```bash
     cd <repo-root>/.claude/worktrees/<dir-name>
     ```
  3. Only then start making changes

- Claude MUST NEVER modify or create files directly on `main` or `develop`. This applies to ALL changes including documentation, configuration, and rule files.

### Branch Naming Conventions

Claude MUST use the following branch prefixes and meanings:

- **feat/**
  General feature development.
  Use when:
  - Application logic
  - Test implementation
  - Infrastructure or CDK-related implementation

- **fix/**
  Bug fixes that correct unintended behavior.
  Use when:
  - Fixing runtime errors, crashes, or exceptions
  - Correcting wrong logic or calculation results
  - Resolving regressions introduced by previous changes
  - Patching security vulnerabilities

- **docs/**
  Documentation updates only.
  Use when:
  - CLAUDE.md, README.md, and other documentation files
  - Specifications, design documents, or proposals (MUST NOT include implementation code)

- **refactor/**
  Code restructuring without changing external behavior.
  Use when:
  - Renaming variables, functions, or classes for clarity
  - Extracting or inlining functions/modules
  - Reorganizing file or directory structure
  - Improving code readability or reducing complexity

- **test/**
  Test-only changes with no production code modifications.
  Use when:
  - Adding missing test coverage
  - Fixing or updating existing tests
  - Refactoring test utilities or fixtures
  - Adding test configuration (e.g., jest.config, pytest.ini)

- **chore/**
  Maintenance tasks that do not affect source or test logic.
  Use when:
  - Updating dependencies or lock files
  - Modifying build scripts or tooling configuration
  - Updating `.gitignore`, linter configs, or editor settings
  - Repository housekeeping (cleaning up unused files)

- **perf/**
  Performance improvements with no functional change.
  Use when:
  - Optimizing algorithms or data structures
  - Reducing bundle size or memory usage
  - Adding caching or memoization
  - Improving query or rendering performance

- **ci/**
  CI/CD pipeline and automation changes only.
  Use when:
  - Adding or modifying CI workflow files (e.g., GitHub Actions, GitLab CI)
  - Updating deployment scripts or release automation
  - Changing CI environment variables or secrets configuration
  - Adjusting build/test/deploy pipeline stages

## Message Language (MUST)

Commit messages, PR titles/descriptions, and PR review comments MUST be written in the same language as the repository's `README.md`. Before writing any commit message or PR description, check the language used in `README.md` and match it.

## Pre-Commit Checklist (MUST)

Claude MUST complete ALL of the following BEFORE creating any commit:

1. **Tests written** — Unit tests (and integration tests if API/DB changes) for all new/changed code
2. **Tests passing** — All tests run and pass (`pytest` / `npx jest`)
   > NOTE: "Tests passing" includes manual functional verification for code that lacks formal test frameworks (shell scripts, CI configs, etc.). `bash -n` or `shellcheck` alone is NOT sufficient — the script must be actually executed in realistic scenarios.
3. **Build passing** — Build verification succeeds (`npx tsc --noEmit` / `npx expo export` / equivalent)
4. **Coverage verified** — Test coverage ≥ 80% for new/changed code
5. **E2E tests run** — If the change affects app behavior (see criteria below), E2E tests MUST be run and pass BEFORE committing. Do NOT skip this step or defer it to "after the PR".

### E2E Test Required Criteria

E2E tests are REQUIRED when the change meets ANY of the following:

- Modifies UI components, screens, or navigation flows
- Changes API endpoints, request/response schemas, or error handling
- Alters authentication, authorization, or session logic
- Modifies form validation, input handling, or user interactions
- Changes business logic that affects user-visible behavior
- Updates state management that impacts what users see or do
- Modifies database schemas or queries that back user-facing features

E2E tests are NOT required for:

- Documentation-only changes
- Code style / linting / formatting changes
- Internal refactoring with no user-visible behavior change (unit tests are sufficient)
- Build configuration or CI pipeline changes
- Adding or updating dev dependencies

When in doubt, run E2E tests. Skipping E2E tests for behavioral changes has caused regressions in the past.

Claude MUST NEVER create a commit or PR without completing these steps. If the user explicitly requests to skip testing, Claude should warn about risks but comply.

This checklist applies to all workflow types (Feature, Bugfix, Refactor, DB Change). The only exception is the **Docs** workflow (documentation-only changes with no code modifications).

## Commit Message Format

```
<type>: <description>

<optional body>
```

Types: feat, fix, refactor, docs, test, chore, perf, ci

## Pull Request Workflow

When creating PRs:
1. Analyze full commit history (not just latest commit)
2. Use `git diff [base-branch]...HEAD` to see all changes
3. Draft comprehensive PR summary (in the same language as `README.md`)
4. Include test plan with TODOs
5. Push with `-u` flag if new branch
6. Clean up worktree — see **Worktree Cleanup (MUST)** below

## Worktree Cleanup (MUST)

PR creation and worktree cleanup are an **atomic operation** — one MUST NOT happen without the other. Immediately after a PR is created, Claude MUST execute the following cleanup steps before responding to the user.

1. Verify the worktree exists:
   ```bash
   git worktree list
   ```
2. Move to the repository root:
   ```bash
   cd <repo-root>
   ```
3. Remove the worktree:
   ```bash
   git worktree remove .claude/worktrees/<dir-name>
   ```
4. Delete the local branch:
   ```bash
   git branch -d <branch-name>
   ```

**Prohibited:**
- NEVER run `rm -rf .claude/worktrees/` or delete the entire worktrees directory
- NEVER remove worktrees or branches that were NOT created in the current session