# AEOS Domain Model

## Purpose

The Domain Model defines the major engineering domains managed by AEOS.

Unlike architectural layers, domains represent engineering responsibilities.

Multiple domains may exist within the same architectural layer.

---

# Domain Overview

```
+--------------------------------------------------+
|                 FOUNDATION                        |
+--------------------------------------------------+

        ↓

+--------------------------------------------------+
|                   KERNEL                          |
+--------------------------------------------------+

        ↓

+--------------------------------------------------+
|                 GOVERNANCE                        |
+--------------------------------------------------+

        ↓

+--------------------------------------------------+
|                  KNOWLEDGE                        |
+--------------------------------------------------+

        ↓

+--------------------------------------------------+
|                 ENGINEERING                       |
+--------------------------------------------------+

        ↓

+--------------------------------------------------+
|               ORCHESTRATION                       |
+--------------------------------------------------+

        ↓

+--------------------------------------------------+
|                  PROJECTS                         |
+--------------------------------------------------+

        ↓

+--------------------------------------------------+
|                   RUNTIME                         |
+--------------------------------------------------+
```

---

# Engineering Domains

## Foundation

Responsible for:

- Charter
- Laws
- Terminology
- Meta Model
- Reference Architecture

---

## Kernel

Responsible for:

- Entity
- Identity
- Lifecycle
- Relationships
- Versioning
- State Management

---

## Governance

Responsible for:

- Policies
- Standards
- Reviews
- Compliance
- Metrics
- Approval Gates

---

## Knowledge

Responsible for:

- Specifications
- ADRs
- Architecture
- Documentation
- Knowledge Graph
- Lessons Learned

---

## Engineering

Responsible for:

- Roles
- Capabilities
- Artifacts
- Templates
- Skills

---

## Orchestration

Responsible for:

- Commands
- Workflows
- Automation
- Scheduling
- Pipelines

---

## Projects

Responsible for:

- Project Packs
- Technology Packs
- Domain Extensions
- Project Configuration

---

## Runtime

Responsible for:

- Cursor Adapter
- Claude Adapter
- Codex Adapter
- Gemini Adapter
- CLI Adapter
- VS Code Adapter

---

# Domain Communication

Domains communicate through published contracts.

No domain may directly modify another domain's internal implementation.

Communication SHALL occur through:

- Specifications
- APIs
- Events
- Contracts

---

# Domain Ownership

Each domain SHALL have:

- Domain Owner
- Architectural Responsibilities
- Public Interfaces
- Versioning Strategy
- Governance Rules

---

# Domain Evolution

New functionality SHOULD extend an existing domain before introducing a new one.

Creation of a new domain requires architectural approval.