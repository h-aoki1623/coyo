# Workflow

## Task Classification

Before starting work, classify the task to select the appropriate workflow:

| Type | When to Use | Key Agents |
|---|---|---|
| **Feature** | New functionality | architect, planner, code-reviewer, security-reviewer, web-e2e-tester / mobile-e2e-tester |
| **Bugfix** | Fixing incorrect behavior | code-reviewer |
| **Refactor** | Restructuring without behavior change | architect, refactor-cleaner, code-reviewer |
| **DB Change** | Schema, migration, query optimization | architect, database-reviewer, security-reviewer |
| **Docs** | Documentation only | doc-updater |

## Common Rules

- If on `main`, create and switch to a new branch before any work
- Follow branch naming conventions in [git.md](git.md)
- Keep branches focused on a single task
- Follow conventional commits format

---

## Feature Workflow

Spec-Driven: define specifications before writing code.

### Phase 1: Requirements (Plan Mode)

1. **Requirements Definition**
   - Clarify ambiguous or incomplete requirements with the user
   - Define scope, constraints, and acceptance criteria
   - Define main screens and user flows (normal flows)
   - Skip if requirements are already clear and well-defined
   - **Scope boundary**: Do NOT make design decisions here (architecture, API structure, DB schema, error handling strategy, UI component structure). Those belong to Phase 2.

> **Mode transition**: Exit Plan Mode (ExitPlanMode) after Phase 1 approval. Phase 2 onwards MUST run in normal mode to enable subagent execution. Do NOT remain in Plan Mode after Phase 1.

### Phase 2: Design

Design elements are executed sequentially. Skip elements not relevant to the feature.

2. **Domain Model Design** - Use **architect** agent
   - Define entities, value objects, and aggregates
   - Establish relationships and business rules
   - This model serves as the foundation for all subsequent designs

3. **API Design** - Use **architect** agent
   - Define endpoints, methods, and URL structure
   - Define request/response contracts (based on domain model)
   - Define authentication and authorization requirements

4. **Database Design** - Use **architect** + **database-reviewer** agents
   - Design schema, tables, indexes, and relations (based on domain model and API contracts)
   - Define constraints, data types, and migration strategy
   - RLS policies (Supabase)

5. **Error Handling Design**
   - Classify expected errors (validation, auth, external API, timeout, etc.)
   - Define error response format and status codes
   - Define retry strategies for transient failures
   - **Mobile**: Include offline/network error handling and retry with connectivity awareness

6. **UI Design** (user-facing features)
   - Design component structure and responsibilities
   - Define state management strategy (client-side state, loading, error display)
   - Design error screens and recovery flows
   - Supplement screens/flows not covered in Phase 1
   - **Mobile**: Define navigation structure, platform-specific adaptations (iOS/Android), and safe area handling

7. **Implementation Plan** - Use **planner** agent
   - Create step-by-step plan based on all design outputs
   - Break down into phases with dependencies and risks
   - Pause for user approval only if the user explicitly requested it

### Phase 3: Implement

8. **Create Branch**
9. **Implementation** (parallel where frontend/mobile and backend are independent)
   - Web frontend: use **frontend-implementer** agent (based on API contracts + UI design)
   - Mobile (React Native): use **mobile-implementer** agent (based on API contracts + UI design)
   - Backend: use **backend-implementer** agent (based on API contracts + DB design)
   - If tightly coupled, implement sequentially
10. **Build Verification**
    - Use **build-error-resolver** if build fails
    - **Mobile (Expo CNG)**: Verify with `npx expo export` and `eas build` (ios/android directories are generated, not committed)

### Phase 4: Verify

11. **Write Tests** - Use **tester** agent
    - Unit tests for business logic and utilities
    - Integration tests for API/DB operations
    - Target 80%+ coverage

12. **Review** (run in parallel where possible)
    - **code-reviewer**: quality, patterns, maintainability
    - **security-reviewer**: vulnerabilities, input validation, secrets (auth/payment/API code)
    - **database-reviewer**: schema, indexes, queries, RLS (DB changes)
    - **python-reviewer**: PEP 8, type hints, Pythonic idioms (Python projects)

13. **E2E Tests** (critical user flows)
    - Web: use **web-e2e-tester** (Playwright)
    - Mobile: use **mobile-e2e-tester** (Maestro)

### Phase 5: Finalize

14. **Commit & Push**
15. **Documentation** (significant changes only)
    - Use **doc-updater** to update codemaps and docs

---

## Bugfix Workflow

Reproduce-First: confirm the bug before fixing.

1. **Investigate** - Use **explorer** agent to trace the bug's root cause
2. **Create Branch**
3. **Reproduce** - Write a failing test or confirm reproduction steps
4. **Fix** - Implement minimal fix
5. **Verify** - Confirm the reproduction test passes
6. **Test Coverage** - Verify reproduction test is sufficient; add tests if needed
   - Unit tests for the fixed behavior
   - Integration tests if the bug spans multiple components
   - E2E tests if the bug affects a user flow - use **web-e2e-tester** (web) or **mobile-e2e-tester** (mobile)
7. **Review** (run in parallel where possible)
   - **code-reviewer**: quality, patterns, maintainability
   - **security-reviewer**: vulnerabilities, input validation, secrets (auth/payment/API code)
   - **python-reviewer**: PEP 8, type hints, Pythonic idioms (Python projects)
8. **Commit & Push**

---

## Refactor Workflow

Safety-Net-First: ensure existing behavior is protected.

1. **Analyze** - Use **refactor-cleaner** to identify dead code and duplicates
2. **Design** - Use **architect** for structural decisions
3. **Create Branch**
4. **Add Safety Tests** - Add tests covering existing behavior before changing code
5. **Refactor** - Execute changes incrementally
6. **Test Coverage** - Verify safety tests still pass; add tests if coverage gaps remain
   - Unit tests to verify refactored code behaves identically
   - Integration tests for changed interfaces or boundaries
   - E2E tests if user-facing behavior could be affected - use **web-e2e-tester** (web) or **mobile-e2e-tester** (mobile)
7. **Review** (run in parallel where possible)
   - **code-reviewer**: quality, patterns, maintainability
   - **security-reviewer**: vulnerabilities, input validation, secrets (auth/payment/API code)
   - **python-reviewer**: PEP 8, type hints, Pythonic idioms (Python projects)
   - **build-error-resolver** if build breaks
8. **Commit & Push**

---

## DB Change Workflow

Schema-First: design the schema before writing application code.

1. **Schema Design** - Use **architect** for data modeling
2. **DB Review** - Use **database-reviewer** for:
   - Index strategy, data types, constraints
   - RLS policies (Supabase)
   - Query performance (EXPLAIN ANALYZE)
3. **Create Branch**
4. **Implement** - Create migrations and application code
5. **Test Coverage** - Verify existing tests pass; add tests for new or changed behavior
   - Unit tests for data access logic
   - Integration tests for migrations and DB operations
   - E2E tests if schema changes affect user flows - use **web-e2e-tester** (web) or **mobile-e2e-tester** (mobile)
6. **Review** (run in parallel where possible)
   - **code-reviewer**: quality, patterns, maintainability
   - **security-reviewer**: RLS, access control, input validation
   - **python-reviewer**: PEP 8, type hints, Pythonic idioms (Python projects)
7. **Commit & Push**

---

## Docs Workflow

Lightweight flow for documentation-only changes.

1. **Create Branch**
2. **Update** - Use **doc-updater** to regenerate codemaps and refresh docs
3. **Verify** - Confirm links work and examples are current
4. **Commit & Push**

