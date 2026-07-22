# Test Design Techniques

## Purpose

Test Design transforms requirements into effective verification scenarios.

The objective is not to maximize the number of test cases, but to maximize confidence while minimizing redundant verification.

---

# Design Principles

Good test design should be:

- Risk-driven
- Traceable
- Repeatable
- Maintainable
- Deterministic

---

# Primary Techniques

## Boundary Value Analysis (BVA)

Focus on values around the limits of valid input.

Example:

Allowed age: 18–60

Recommended tests:

17

18

19

59

60

61

---

## Equivalence Partitioning

Divide inputs into groups expected to behave identically.

Instead of testing every value, verify one representative from each partition.

---

## Decision Table Testing

Useful when multiple conditions determine the outcome.

Example:

Subscription

Login

Region

Payment Status

↓

Expected Feature Access

---

## State Transition Testing

Applicable when behavior depends on system state.

Example:

Draft

↓

Submitted

↓

Approved

↓

Archived

Verify valid transitions and reject invalid ones.

---

## Pairwise Testing

Reduce combinations by testing all significant pairs instead of every permutation.

Ideal for configuration-heavy systems.

---

## Use Case Testing

Validate complete user journeys.

Focus on business outcomes rather than individual functions.

---

## Exploratory Testing

Engineers investigate behavior without predefined scripts.

Best suited for:

- Complex UI
- New features
- High-risk areas
- Regression discovery

---

# Anti-Patterns

Avoid:

- Duplicate scenarios
- Trivial happy-path-only testing
- One assertion per requirement without context
- Excessive low-value combinations

---

# AI Guidance

When generating test cases:

1. Identify risk.
2. Select appropriate design technique.
3. Prefer minimal but sufficient coverage.
4. Eliminate redundant scenarios.
5. Ensure traceability to requirements.