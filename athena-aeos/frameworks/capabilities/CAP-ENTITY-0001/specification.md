# CAP-ENTITY-0001

| Property | Value |
|----------|-------|
| ID | CAP-ENTITY-0001 |
| Version | 0.1.0 |
| Status | Draft |
| Layer | Framework |
| Owner | Chief Systems Architect |

---

# Purpose

Defines the canonical engineering capability entity.

Capabilities describe reusable engineering functions without prescribing implementation.

---

# Entity Schema

Every Capability SHALL define

- Identity
- Name
- Description
- Purpose
- Inputs
- Outputs
- Preconditions
- Postconditions
- Executor Types
- Required Skills
- Related Artifacts
- Related Specifications
- Relationships
- Lifecycle
- Metadata
- Version

---

# Capability Categories

Supported categories

- Architecture
- Development
- Testing
- Security
- Documentation
- Deployment
- Governance
- Operations
- AI
- Analytics

Projects MAY introduce additional categories.

---

# Executor Types

A Capability MAY be executed by

- Human
- Team
- AI Agent
- Service
- Automation Pipeline
- External System

---

# Inputs

Capabilities MAY consume

- Artifacts
- Specifications
- Source Code
- Configuration
- Policies
- Knowledge Assets

---

# Outputs

Capabilities MAY produce

- Artifacts
- Reports
- Specifications
- Decisions
- Metrics
- Logs

---

# Relationships

Capability MAY

IMPLEMENTED_BY Role

USED_IN Workflow

GOVERNED_BY Policy

PRODUCES Artifact

CONSUMES Artifact

REFERENCES Specification

DEPENDS_ON Capability

---

# Validation Rules

Every Capability SHALL

✓ have unique identity

✓ define purpose

✓ define inputs

✓ define outputs

✓ define lifecycle

Capability SHALL NOT

✗ depend on implementation

✗ assign specific executors

✗ violate framework contract