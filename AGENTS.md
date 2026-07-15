# AGENTS.md

## Primary Rule

Code simplicity is the number-one priority.

## Simplicity First

- Implement the smallest solution that satisfies the current requirement.
- Prefer direct, readable code over abstractions.
- Prefer a few small files over an elaborate architecture.
- Do not introduce design patterns unless a current requirement clearly needs them.
- Do not create frameworks for hypothetical future features.
- Do not optimize prematurely.
- Avoid unnecessary dependencies.
- Prefer standard-library functionality where practical.
- Avoid configuration options until there is a real need for them.
- Keep data structures obvious and easy to inspect.

## Build The Happy Path First

- Implement the normal successful workflow before supporting uncommon edge cases.
- Do not add an `if`, fallback, retry, wrapper, or validation branch for every imaginable scenario.
- Add defensive handling only for cases that are likely, dangerous, or already observed.
- Avoid deeply nested conditionals.
- Avoid speculative compatibility layers.
- When uncertainty exists, choose the simplest behavior and document the limitation.

## Testing Approach

- Do not begin by creating a large test suite.
- First make the core workflow work end to end.
- Use a small smoke test or manual fixture to verify the MVP.
- Add focused automated tests after the design becomes stable.
- Add tests when fixing an actual bug or protecting important behavior.
- Do not create tests for hypothetical edge cases during the first implementation.
- Keep tests simple and behavior-focused.
- Do not overuse mocks.

Correctness still matters. Validate the core behavior without building a complex defensive system before the product has proven its shape.

## Refactoring Rules

- Do not refactor working code merely to make it more abstract.
- Extract a helper only when duplication or complexity is already visible.
- Prefer deleting code to adding indirection.
- Keep functions short enough to understand, but do not split straightforward logic into many tiny functions.
- Make one clear improvement at a time.
- Preserve a runnable state after each meaningful step.

## Scope Control For Version 0.1

Explicitly postpone:

- Interactive graph editing.
- Multiple graph themes.
- Complex graph-layout algorithms.
- Database storage.
- Cloud synchronization.
- Historical analytics.
- Multi-user collaboration.
- Extensive configuration.
- Comprehensive support for unusual tool types.
- Automatic inference of every possible reasoning relationship.
- A large testing matrix.
- Performance optimization before there is evidence it is needed.
