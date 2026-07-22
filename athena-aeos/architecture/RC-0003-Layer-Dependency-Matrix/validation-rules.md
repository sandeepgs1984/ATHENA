# Dependency Validation Rules

## Repository Validation

Every specification SHALL satisfy the following:

- Reference only permitted layers.
- Avoid circular dependencies.
- Maintain directional dependency flow.
- Preserve layer responsibilities.

---

## Validation Outcomes

A dependency review should verify:

- No prohibited layer references.
- No reverse dependencies.
- No cyclic relationships.
- No responsibility leakage.

---

## Exceptions

Exceptions require an approved Architecture Decision Record.