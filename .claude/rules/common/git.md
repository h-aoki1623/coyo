# Git

### Branching Rules (MUST)

- **Before making any file modifications or creating new files**, Claude MUST check the current git branch.
- If the current git branch is `main` or `develop`, Claude MUST:
  1. Create a new worktree with a new branch using git commands:
     ```bash
     git worktree add .claude/worktrees/<branch-name> -b <branch-name>
     ```
  2. Move into the worktree directory:
     ```bash
     cd <repo-root>/.claude/worktrees/<branch-name>
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

Commit messages and PR titles/descriptions MUST be written in the same language as the repository's `README.md`. Before writing any commit message or PR description, check the language used in `README.md` and match it.

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
6. After the PR is created, clean up the worktree and local branch:
   ```bash
   cd <repo-root>
   git worktree remove .claude/worktrees/<branch-name>
   git branch -d <branch-name>
   ```