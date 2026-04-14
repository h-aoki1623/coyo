# Coyo — Project Instructions

## Workflow Compliance (MUST)

Before starting ANY task, Claude MUST follow these steps in order. No steps may be skipped regardless of task size or perceived simplicity.

1. **Classify** the task type (Feature / Bugfix / Refactor / DB Change / Docs) per `.claude/rules/common/workflow.md`
2. **Look up** the required agents and phases for that workflow type in `workflow.md`
3. **Create a task checklist** listing every required agent and verification step before writing any code
4. **Execute each step** using the designated agent — never perform an agent's job directly
5. **Verify gate conditions** are met before proceeding to the next phase (see workflow.md for gate conditions)

