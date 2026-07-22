# Cross-Layer Relationships

## Relationship Principles

### CR-001 — Explicit Relationships

Cross-layer relationships SHALL be documented explicitly.

---

### CR-002 — No Implicit Dependencies

A documented relationship does NOT imply a software dependency.

---

### CR-003 — Traceability

Relationships SHOULD support traceability from high-level concepts to runtime execution.

---

## Relationship Catalog

| Source | Relationship | Target |
|---------|--------------|--------|
| Foundation | Defines | Kernel |
| Kernel | Enables | Engineering |
| Engineering | Governed By | Governance |
| Governance | Validates | Knowledge |
| Knowledge | Consumed By | Runtime |
| Runtime | Supports | Applications |

---

## Runtime Relationships

| Runtime Concept | Related Knowledge Concept |
|-----------------|---------------------------|
| Runtime Entity | Knowledge Entity |
| Runtime Session | Workflow |
| Runtime Command | Capability |
| Runtime Pipeline | Workflow |
| Runtime Event | Trace |
| Runtime State | Metadata |

---

## Summary

The relationship map provides a repository-wide view of how concepts collaborate while preserving architectural independence.