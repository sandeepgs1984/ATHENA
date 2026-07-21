# AEOS Dependency Model

## Purpose

This document defines the dependency rules between architectural layers within AEOS.

The objective is to prevent circular dependencies, architectural drift, and hidden coupling.

---

# Dependency Principle

A layer SHALL only depend on layers beneath it.

Higher layers consume services from lower layers.

Lower layers SHALL NEVER depend on higher layers.

---

# Dependency Graph

```
09 Tools
    │
    ▼
08 Reference
    │
    ▼
07 Runtime
    │
    ▼
06 Projects
    │
    ▼
05 Orchestration
    │
    ▼
04 Engineering
    │
    ▼
03 Knowledge
    │
    ▼
02 Governance
    │
    ▼
01 Kernel
    │
    ▼
00 Foundation
```

---

# Allowed Dependencies

| Layer | Depends On |
|---------|------------|
| Foundation | None |
| Kernel | Foundation |
| Governance | Foundation, Kernel |
| Knowledge | Foundation, Kernel, Governance |
| Engineering | Foundation, Kernel, Governance, Knowledge |
| Orchestration | Engineering |
| Projects | Orchestration |
| Runtime | Projects |
| Reference | Runtime |
| Tools | All Layers (read-only) |

---

# Dependency Rules

## Rule 1

Lower layers SHALL NEVER depend on higher layers.

---

## Rule 2

Circular dependencies are prohibited.

---

## Rule 3

Cross-layer communication shall occur only through published interfaces.

---

## Rule 4

Shared functionality SHALL reside in the lowest appropriate layer.

---

## Rule 5

Project Packs SHALL NOT modify Foundation or Kernel behavior.

---

# Architectural Example

Correct

```
Workflow

↓

Capability

↓

Knowledge

↓

Kernel
```

Incorrect

```
Kernel

↓

Workflow
```

---

# Compliance

Every specification SHALL declare:

- Target Layer
- Direct Dependencies
- Architectural Impact