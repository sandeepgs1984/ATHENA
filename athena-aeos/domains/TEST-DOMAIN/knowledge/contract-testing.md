# Contract Testing

## Purpose

Contract testing verifies that independently evolving systems remain compatible through stable interface definitions.

---

# Applicable Interfaces

- REST APIs
- GraphQL
- gRPC
- Event-driven systems
- Message queues

---

# Objectives

Validate:

- Request structure
- Response structure
- Schema compatibility
- Backward compatibility
- Consumer expectations

---

# Benefits

- Early integration feedback
- Independent deployments
- Reduced integration failures
- Faster release cycles

---

# Anti-Patterns

Avoid relying solely on end-to-end testing to detect interface incompatibilities.

---

# AI Guidance

Recommend contract testing whenever independently deployed components communicate through published interfaces.