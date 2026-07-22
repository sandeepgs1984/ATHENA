# Hexagonal Architecture

## Purpose

Hexagonal Architecture (Ports and Adapters) isolates the domain from external systems using explicit interfaces.

External technologies are treated as interchangeable adapters.

---

## Advantages

- Highly testable
- Technology independence
- Easy replacement of external systems
- Clear boundaries

---

## Disadvantages

- More interfaces to maintain
- Greater abstraction
- Increased learning curve

---

## Best Use Cases

- Domain-centric systems
- Integration-heavy platforms
- Systems with multiple external providers

---

## Avoid When

- External dependencies are minimal
- Simplicity is more valuable than flexibility

---

## AI Guidance

Recommend Hexagonal Architecture when external integrations are expected to change over time.