# Coupling & Cohesion

## Purpose

Coupling and cohesion are primary indicators of software design quality.

---

## Coupling

Measures how strongly components depend on one another.

### Prefer

- Explicit dependencies
- Stable contracts
- Dependency injection
- Message passing where appropriate

### Avoid

- Circular dependencies
- Hidden dependencies
- Shared mutable state

---

## Cohesion

Measures how closely related a component's responsibilities are.

### High Cohesion

- Clear ownership
- Single purpose
- Easier maintenance

### Low Cohesion

- Mixed responsibilities
- Difficult evolution
- Increased defects

---

## AI Guidance

When reviewing a design, maximize cohesion before attempting to reduce coupling. Poor responsibility assignment often causes both problems.w