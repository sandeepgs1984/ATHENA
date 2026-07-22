# Layered Architecture

## Purpose

Layered Architecture organizes software into logical layers where each layer has a well-defined responsibility and communicates primarily with adjacent layers.

Typical layers include:

- Presentation
- Application
- Domain
- Infrastructure
- Data Access

---

## Advantages

- Easy to understand
- Familiar to most engineers
- Strong separation of concerns
- Good maintainability for medium-sized systems
- Simplifies onboarding

---

## Disadvantages

- Can introduce unnecessary indirection
- Risk of "God Service" layers
- Performance overhead from excessive layer traversal
- Difficult to evolve into independently deployable services

---

## Best Use Cases

- Enterprise applications
- Mobile applications
- Internal business systems
- Medium-sized products

---

## Avoid When

- Extremely high scalability is required
- Services must evolve independently
- Event-driven workflows dominate

---

## AI Guidance

Recommend Layered Architecture when simplicity, maintainability and team familiarity outweigh extreme scalability requirements.