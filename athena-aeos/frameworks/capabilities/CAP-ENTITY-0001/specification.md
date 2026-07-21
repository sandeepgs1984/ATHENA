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

# Inheritance

Capability extends the canonical Entity defined by MM-0001.

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

# Capability-Specific Attributes

The Capability Entity adds the following attributes:

- Purpose
- Inputs
- Outputs
- Preconditions
- Postconditions
- Executor Types
- Required Skills
- Success Criteria
- Performance Metrics

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

In addition to the validation inherited from MM-0001:

Every Capability SHALL:

- Define a purpose.
- Define inputs.
- Define outputs.
- Define at least one supported executor type.

A Capability MAY define:

- Preconditions.
- Postconditions.
- Success criteria.
- Performance metrics.

A Capability SHALL NOT:

- Redefine inherited Entity properties.
- Assign a specific executor.
- Override Kernel behavior.
- Duplicate Meta Model definitions.
