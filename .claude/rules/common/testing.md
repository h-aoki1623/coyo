# Testing Requirements

## Minimum Test Coverage: 80%

Test Types:
1. **Unit Tests** - Individual functions, utilities, components - use **tester**
2. **Integration Tests** - API endpoints, database operations - use **tester**
3. **E2E Tests** - Critical user flows - use **web-e2e-tester** (web) or **mobile-e2e-tester** (mobile)

## Testing Strategy by Workflow

Testing timing and approach vary by workflow type (see [workflow.md](workflow.md)):

| Workflow | When to Test | Approach |
|---|---|---|
| **Feature** | After implementation (Phase 4) | Use **tester** for unit + integration, **web-e2e-tester** (web) or **mobile-e2e-tester** (mobile) for E2E |
| **Bugfix** | Before fix (reproduction) + after fix (coverage check) | Reproduction test first, then verify coverage |
| **Refactor** | Before refactor (safety net) + after refactor (coverage check) | Safety tests first, then verify behavior preserved |
| **DB Change** | After implementation | Focus on integration tests for migrations and queries |

## Edge Cases (MUST Test)

1. **Null/Undefined** - What if input is null or undefined?
2. **Empty** - What if array/string/object is empty?
3. **Invalid Types** - What if wrong type is passed?
4. **Boundaries** - Min/max values, off-by-one errors
5. **Error Paths** - Network failures, database errors, timeout
6. **Special Characters** - Unicode, emojis, SQL special characters

## Test Quality Rules

- Test behavior, not implementation details
- Tests must be independent (no shared mutable state)
- Use descriptive test names describing what is tested
- Arrange-Act-Assert structure
- Mock external dependencies for isolation
- One assertion per test (or logically related assertions)
- Keep tests fast (unit tests < 50ms each)
- Clean up after tests (no side effects between tests)
- Review coverage reports to identify gaps

## Common Anti-Patterns

1. **Testing Implementation Details** - Test user-visible behavior, not internal state or private methods
2. **Brittle Selectors** - Use semantic selectors (role, testid, text) over CSS classes
3. **No Test Isolation** - Each test must set up its own data; never depend on previous test results

## Test File Placement

| Test Type | Frontend (TypeScript) | Backend (Python) |
|---|---|---|
| **Unit** | Colocated: `*.test.tsx` next to source | `tests/unit/test_*.py` |
| **Integration** | `tests/integration/*.test.ts` | `tests/integration/test_*.py` |
| **E2E** | Top-level `/e2e/` (shared across FE+BE) | — |

## Troubleshooting Test Failures

1. Check test isolation
2. Verify mocks are correct
3. Fix implementation, not tests (unless tests are wrong)

## Agent Support

- **tester** - Unit tests + integration tests
- **web-e2e-tester** - Web E2E tests (Playwright)
- **mobile-e2e-tester** - Mobile E2E tests (Maestro)
