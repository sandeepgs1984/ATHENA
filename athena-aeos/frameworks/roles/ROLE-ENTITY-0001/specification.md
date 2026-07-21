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

# Inheritance

Role extends the canonical Entity defined by MM-0001.

Inherited properties include:

- Identity
- Metadata
- Lifecycle
- Version
- Relationships
- Validation
- Audit Information

These properties are defined by MM-0001 and SHALL NOT be redefined here.

---

# Role-Specific Attributes

The Role Entity adds the following attributes to the canonical Entity:

- Responsibilities
- Authorities
- Decision Rights
- Required Skills
- Required Capabilities
- Organizational Scope
- Assignment Constraints

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

In addition to the validation inherited from MM-0001:

Every Role SHALL:

- Define responsibilities.
- Define authorities.
- Define decision rights.
- Define required capabilities.

A Role MAY define:

- Required certifications.
- Organizational scope.
- Delegation rules.

A Role SHALL NOT:

- Redefine inherited Entity properties.
- Override Kernel behavior.
- Duplicate Meta Model definitions.