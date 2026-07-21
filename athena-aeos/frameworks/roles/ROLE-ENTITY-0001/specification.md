# ROLE-ENTITY-0001

| Property | Value |
|----------|-------|
| ID | ROLE-ENTITY-0001 |
| Version | 0.1.0 |
| Status | Draft |
| Layer | Framework |
| Owner | Chief Systems Architect |

---

# Purpose

Defines the canonical engineering role entity.

---

# Entity Schema

Every Role SHALL define

- Identity
- Name
- Description
- Responsibilities
- Authorities
- Decision Rights
- Skills
- Required Capabilities
- Relationships
- Lifecycle
- Metadata
- Version

---

# Role Categories

Supported categories

- Executive
- Architecture
- Engineering
- Quality
- Product
- Security
- Operations
- AI Agent

Projects MAY introduce additional categories.

---

# Responsibilities

A role MAY own

- Specifications
- Reviews
- Approvals
- Decisions
- Governance
- Deliverables

---

# Relationships

Role MAY

IMPLEMENT Capability

PARTICIPATE_IN Workflow

GOVERN Policy

OWN Artifact

AUTHOR Specification

REVIEW Specification

APPROVE Specification

---

# Validation Rules

Every Role SHALL

✓ have unique identity

✓ define responsibilities

✓ define lifecycle

✓ define owner

Role SHALL NOT

✗ create circular ownership

✗ bypass governance

✗ violate framework contract