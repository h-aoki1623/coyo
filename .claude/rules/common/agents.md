# Agent Orchestration

## Available Agents

Located in `~/.claude/agents/`:

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| planner | Implementation planning | Feature workflow: Phase 2 |
| architect | System design, trade-off analysis | Feature, Refactor, DB Change workflows |
| frontend-implementer | Web frontend implementation (components, state, API integration) | Feature workflow: Phase 3 (Web) |
| mobile-implementer | React Native implementation (screens, navigation, platform-specific code) | Feature workflow: Phase 3 (Mobile) |
| backend-implementer | Backend implementation (API, DB, business logic) | Feature workflow: Phase 3 |
| code-reviewer | Code quality review | All workflows (Review step) |
| security-reviewer | Vulnerability detection | All workflows (Review step) |
| database-reviewer | Schema, query, RLS review | Feature (DB changes), DB Change workflow |
| python-reviewer | PEP 8, type hints, Pythonic idioms | All workflows (Python projects) |
| tester | Unit tests + integration tests | All workflows (Test writing step) |
| web-e2e-tester | E2E testing (Playwright, web) | All workflows (E2E test step, Web) |
| mobile-e2e-tester | Mobile E2E testing (Maestro) | All workflows (E2E test step, Mobile) |
| build-error-resolver | Fix build/type errors | When build fails |
| refactor-cleaner | Dead code detection, cleanup | Refactor workflow |
| doc-updater | Codemaps, documentation | Feature workflow: Phase 5 |
| python-advisor | Python education, Q&A | On-demand (not in workflows) |

## Automatic Agent Selection

Select agents based on workflow type (see [workflow.md](workflow.md)):

| Workflow | Agents Used |
|---|---|
| **Feature (Web)** | architect → planner → frontend-implementer ‖ backend-implementer → build-error-resolver → tester → code-reviewer ‖ security-reviewer ‖ database-reviewer ‖ python-reviewer → web-e2e-tester → doc-updater |
| **Feature (Mobile)** | architect → planner → mobile-implementer ‖ backend-implementer → build-error-resolver → tester → code-reviewer ‖ security-reviewer ‖ database-reviewer ‖ python-reviewer → mobile-e2e-tester → doc-updater |
| **Bugfix** | explorer → code-reviewer ‖ security-reviewer ‖ python-reviewer |
| **Refactor** | refactor-cleaner → architect → code-reviewer ‖ security-reviewer ‖ python-reviewer ‖ build-error-resolver |
| **DB Change** | architect → database-reviewer → security-reviewer ‖ code-reviewer ‖ python-reviewer |
| **Docs** | doc-updater |

`→` = sequential, `‖` = parallel

## Parallel Task Execution

ALWAYS use parallel Task execution for independent operations:

```markdown
# GOOD: Parallel execution (Review step)
Launch agents in parallel:
1. code-reviewer: quality review
2. security-reviewer: vulnerability check
3. python-reviewer: PEP 8 compliance

# BAD: Sequential when unnecessary
First code-reviewer, then security-reviewer, then python-reviewer
```
