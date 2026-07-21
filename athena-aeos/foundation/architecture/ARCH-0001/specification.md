# ARCH-0001 — AEOS Reference Architecture

| Property | Value |
|----------|-------|
| ID | ARCH-0001 |
| Version | 1.0.0 |
| Status | Approved |
| Category | Reference Architecture |
| Owner | Chief Systems Architect |

---

# Purpose

The Reference Architecture defines the structural organization of AEOS.

Every implementation SHALL conform to this architecture.

---

# Architectural Principles

- Layered architecture
- Dependency inversion
- Separation of concerns
- Composability
- Vendor neutrality
- Knowledge-centric design

---

# Architecture Layers

```
00 Foundation
│
01 Kernel
│
02 Governance
│
03 Knowledge
│
04 Engineering
│
05 Orchestration
│
06 Projects
│
07 Runtime
│
08 Reference
│
09 Tools
```

---

# Layer Responsibilities

## 00 Foundation

Defines constitutional specifications.

Includes:

- Charter
- Laws
- Terminology
- Meta Model
- Reference Architecture

---

## 01 Kernel

Provides the core execution model.

Responsibilities:

- Entity
- Identity
- Lifecycle
- Relationships
- Versioning
- State Management

---

## 02 Governance

Responsible for:

- Policies
- Reviews
- Compliance
- Metrics
- Approval Gates

---

## 03 Knowledge

Responsible for:

- Knowledge Graph
- ADR
- Specifications
- Architecture
- Lessons Learned

---

## 04 Engineering

Responsible for:

- Roles
- Capabilities
- Artifacts
- Skills
- Templates

---

## 05 Orchestration

Responsible for:

- Commands
- Workflow Engine
- Scheduling
- Automation
- Pipelines

---

## 06 Projects

Responsible for:

- Project Packs
- Domain Extensions
- Technology Extensions

---

## 07 Runtime

Responsible for:

- Cursor
- Claude
- Codex
- Gemini
- CLI
- VS Code

---

## 08 Reference

Provides:

- Sample Implementations
- Examples
- Tutorials
- Best Practices

---

## 09 Tools

Provides:

- Validators
- Generators
- Migration Tools
- Documentation Utilities

---

# Dependency Rules

Layers SHALL only depend on lower layers.

Example:

Runtime

↓

Projects

↓

Orchestration

↓

Engineering

↓

Knowledge

↓

Governance

↓

Kernel

↓

Foundation

Circular dependencies are prohibited.

---

# Extension Rules

New functionality SHALL extend existing layers before introducing new architectural layers.

---

# Conformance

Every specification SHALL identify:

- Target Layer
- Dependencies
- Architectural Impact