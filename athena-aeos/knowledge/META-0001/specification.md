# META-0001

| Property | Value |
|----------|-------|
| ID | META-0001 |
| Version | 0.1.0 |
| Status | Draft |
| Layer | Knowledge |
| Owner | Chief Systems Architect |

---

# Purpose

Define the canonical metadata associated with every AEOS knowledge asset.

Metadata describes an asset but does not define its semantics, identity, or implementation.

---

# Mandatory Metadata

Every knowledge asset SHALL include:

- Identifier
- Title
- Version
- Status
- Layer
- Owner
- Created Date
- Last Updated
- Description

---

# Optional Metadata

Assets MAY include:

- Authors
- Reviewers
- Tags
- Keywords
- Dependencies
- Related Specifications
- Change History
- Approval Date

---

# Metadata Principles

Metadata SHALL:

- Be human-readable.
- Be machine-readable.
- Be versioned.
- Remain independent of implementation.

Metadata SHALL NOT:

- Duplicate content.
- Replace identifiers.
- Replace specifications.

---

# Metadata Lifecycle

Metadata progresses through:

1. Created
2. Updated
3. Reviewed
4. Approved
5. Archived

Each update SHALL preserve version history.

---

# Architectural Boundaries

The Metadata Model SHALL:

- Describe knowledge assets.
- Support governance.
- Support search and indexing.
- Support automation.

The Metadata Model SHALL NOT:

- Define engineering behavior.
- Define semantic meaning.
- Store implementation logic.

---

# Related Specifications

- KN-0001
- ONTO-0001
- NS-0001
- ID-0001

---

# Summary

The Metadata Model standardizes descriptive information across AEOS, ensuring every knowledge asset is consistently documented, searchable, and traceable.