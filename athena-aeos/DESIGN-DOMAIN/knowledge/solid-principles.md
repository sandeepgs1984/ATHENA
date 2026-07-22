# SOLID Principles

## Purpose

SOLID principles improve maintainability, extensibility and testability by encouraging well-structured object-oriented designs.

---

## Single Responsibility Principle (SRP)

A class or module should have one primary reason to change.

### Benefits

- Easier maintenance
- Improved readability
- Better testability

### Risks of Violation

- God Objects
- Feature coupling
- Difficult testing

---

## Open/Closed Principle (OCP)

Software entities should be open for extension but closed for modification.

### Benefits

- Safer evolution
- Reduced regression risk

### Avoid

Creating excessive abstractions for hypothetical future needs.

---

## Liskov Substitution Principle (LSP)

Derived types must behave as valid substitutes for their base types without altering expected behavior.

### Signs of Violation

- Unexpected exceptions
- Conditional logic based on subtype
- Broken client expectations

---

## Interface Segregation Principle (ISP)

Clients should not depend on methods they do not use.

Prefer focused interfaces over large, generalized contracts.

---

## Dependency Inversion Principle (DIP)

Depend upon abstractions rather than concrete implementations.

Benefits:

- Easier testing
- Improved flexibility
- Reduced coupling

---

## AI Guidance

Recommend SOLID principles to improve maintainability, not simply to increase abstraction. Challenge abstractions that add complexity without measurable benefit.