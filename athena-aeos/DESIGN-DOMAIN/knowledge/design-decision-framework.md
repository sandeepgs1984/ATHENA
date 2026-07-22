# Design Decision Framework

## Purpose

Software design decisions should be intentional, explainable and repeatable.

This framework provides a structured approach for evaluating design alternatives.

---

# Decision Flow

Requirements

↓

Responsibilities

↓

Boundaries

↓

Dependencies

↓

Interfaces

↓

Trade-off Analysis

↓

Complexity Assessment

↓

Design Review

↓

Implementation

↓

Continuous Refactoring

---

## Step 1 — Understand the Requirement

Define:

- Functional behavior
- Non-functional expectations
- Constraints
- Expected evolution

Avoid designing before understanding the problem.

---

## Step 2 — Assign Responsibilities

Determine:

- What each component owns
- What each component should not own
- Ownership boundaries
- Collaboration model

---

## Step 3 — Define Boundaries

Separate concerns using logical modules with clear contracts.

Avoid unnecessary cross-module knowledge.

---

## Step 4 — Evaluate Dependencies

Assess:

- Dependency direction
- Coupling
- Stability
- Testability
- Replaceability

---

## Step 5 — Review Complexity

Question every abstraction:

- Does it solve a recurring problem?
- Does it improve maintainability?
- Can it be explained simply?
- Is there a simpler alternative?

---

## Step 6 — Review Trade-offs

Document:

- Benefits
- Drawbacks
- Future flexibility
- Implementation cost

---

## Common Anti-Patterns

Avoid:

- God Objects
- Deep inheritance trees
- Circular dependencies
- Leaky abstractions
- Premature generalization
- Feature envy
- Shotgun surgery

---

## AI Guidance

When reviewing a design:

1. Understand the requirement.
2. Identify responsibilities.
3. Evaluate cohesion and coupling.
4. Review dependency direction.
5. Challenge unnecessary abstractions.
6. Recommend the simplest maintainable design.
7. Explain every recommendation with its trade-offs.