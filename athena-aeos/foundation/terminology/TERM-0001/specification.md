# TERM-0001 — Naming Convention

| Property | Value |
|----------|-------|
| ID | TERM-0001 |
| Version | 0.2.0 |
| Status | Draft |
| Layer | Foundation |
| Owner | Chief Systems Architect |

---

# Purpose

This specification defines the canonical naming convention used throughout the AI Engineering Operating System (AEOS).

It standardizes identifiers, directory names, document names, and numbering rules to ensure consistency, traceability, and long-term maintainability.

---

# Objectives

The naming convention SHALL:

- Provide globally unique identifiers.
- Maintain consistency across the repository.
- Improve discoverability.
- Support automation.
- Enable future extensibility.

---

# Repository Prefixes

## Foundation

| Prefix | Description |
|---------|-------------|
| AESS | AEOS Specification |
| LAW | Engineering Law |
| TERM | Terminology |
| MM | Meta Model |
| ARCH | Reference Architecture |

---

## Kernel

| Prefix | Description |
|---------|-------------|
| KS | Kernel Service |
| KERNEL-ARCH | Kernel Architecture |

---

## Framework Foundation

| Prefix | Description |
|---------|-------------|
| FW | Framework Contract |

---

## Engineering Frameworks

| Prefix | Description |
|---------|-------------|
| ROLE | Role Framework |
| ROLE-ENTITY | Role Entity |
| CAP | Capability Framework |
| CAP-ENTITY | Capability Entity |
| WF | Workflow Framework |
| WF-ENTITY | Workflow Entity |
| POL | Policy Framework |
| POL-ENTITY | Policy Entity |
| ART | Artifact Framework |
| ART-ENTITY | Artifact Entity |
| SPEC | Specification Framework |
| SPEC-ENTITY | Specification Entity |

---

## Governance

| Prefix | Description |
|---------|-------------|
| ADR | Architecture Decision Record |
| RFC | Request for Comments |
| REV | Architecture Review |
| DEC | Engineering Decision |
| CHG | Change Log |

---

# Identifier Format

Every specification SHALL follow:

```
<PREFIX>-<NUMBER>
```

Examples

```
KS-0001

ROLE-0001

CAP-ENTITY-0001

ADR-0001
```

---

# Numbering Rules

- Numbers SHALL contain four digits.
- Numbering SHALL begin at 0001.
- Numbers SHALL never be reused.
- Deprecated specifications SHALL retain their identifiers.
- Renaming SHALL NOT change identifiers.

---

# Directory Naming

Each specification SHALL reside in its own directory.

Example

```
KS-0001/

ROLE-0001/

ROLE-ENTITY-0001/
```

---

# File Naming

Standard files

```
README.md

specification.md

review.md

decisions.md

changelog.md
```

Optional directories

```
diagrams/

examples/

templates/
```

---

# Reserved Prefixes

The following prefixes are reserved and SHALL NOT be reused:

- AESS
- LAW
- TERM
- MM
- ARCH
- KS
- FW
- ROLE
- ROLE-ENTITY
- CAP
- CAP-ENTITY
- WF
- WF-ENTITY
- POL
- POL-ENTITY
- ART
- ART-ENTITY
- SPEC
- SPEC-ENTITY
- ADR
- RFC
- REV
- DEC
- CHG

---

# Extension Rules

Projects MAY introduce additional prefixes.

Additional prefixes SHALL:

- Be documented.
- Avoid conflicts.
- Follow the same naming format.

---

# Examples

```
Foundation

MM-0001

Kernel

KS-0004

Framework

ROLE-0001

Entity

CAP-ENTITY-0001

Governance

ADR-0012
```

---

# Related Specifications

- AESS-0000
- LAW-0001
- MM-0001
- ARCH-0001
- FW-0000

---

# Summary

The Naming Convention establishes the canonical identifier system for AEOS.

All future specifications SHALL comply with this convention.