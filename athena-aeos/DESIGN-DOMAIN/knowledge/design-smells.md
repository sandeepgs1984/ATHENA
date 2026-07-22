# Design Smells

## Purpose

Design Smells are indicators that a software design may become difficult to understand, maintain or evolve.

A smell is not necessarily a defect—it is a signal that warrants investigation.

---

## Common Design Smells

### God Object

One component owns too many responsibilities.

Indicators:

- Excessive size
- Numerous dependencies
- Frequent modifications

Recommendation:

Split responsibilities using cohesive boundaries.

---

### Shotgun Surgery

A single change requires modifications across many modules.

Recommendation:

Improve responsibility assignment and encapsulation.

---

### Feature Envy

A component frequently accesses another component's internal data.

Recommendation:

Move behavior closer to the data it primarily uses.

---

### Primitive Obsession

Business concepts are represented using primitive types rather than meaningful domain abstractions.

Recommendation:

Introduce value objects where they simplify reasoning.

---

### Circular Dependencies

Modules depend on each other directly or indirectly.

Recommendation:

Break dependency cycles using interfaces or redesigned ownership.

---

### Inappropriate Intimacy

Components know too much about each other's implementation.

Recommendation:

Strengthen encapsulation and clarify public contracts.

---

## AI Guidance

Identify design smells as opportunities for improvement, not automatic defects. Recommend changes only when maintainability or adaptability measurably improves.