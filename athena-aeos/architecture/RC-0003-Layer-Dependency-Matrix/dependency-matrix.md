# Layer Dependency Matrix

## Layer Stack

| Layer | May Depend On |
|--------|---------------|
| Foundation | None |
| Kernel | Foundation |
| Engineering | Kernel, Foundation |
| Governance | Engineering, Kernel, Foundation |
| Knowledge | Governance, Engineering, Kernel, Foundation |
| Runtime | Knowledge, Governance, Engineering, Kernel, Foundation |
| Applications | Runtime, Knowledge, Governance, Engineering, Kernel, Foundation |

---

## Dependency Principles

### DP-001 — Downward Dependencies

A layer MAY depend only on layers beneath it.

---

### DP-002 — No Upward Dependencies

A lower layer SHALL NOT depend on a higher layer.

---

### DP-003 — No Circular Dependencies

Architectural layers SHALL NOT form dependency cycles.

---

### DP-004 — Stable Foundations

Lower layers SHOULD change less frequently than higher layers.

---

### DP-005 — Explicit Exceptions

Any exception to these rules SHALL be documented by an approved ADR.

---

## Summary

The dependency matrix preserves architectural integrity by defining a clear direction for dependencies across all layers.