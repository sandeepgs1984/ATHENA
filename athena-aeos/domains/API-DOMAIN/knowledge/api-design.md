# API Design Guidelines

## Purpose

This document defines universal API design guidelines applicable to REST, GraphQL, gRPC, and other API styles.

---

# Resource Modeling

Design APIs around business capabilities and domain concepts rather than database tables.

---

# Naming

API names should be:

- Consistent
- Predictable
- Business-oriented
- Stable

Avoid implementation-specific terminology.

---

# Operations

Every operation should have a single, clearly defined responsibility.

Avoid multi-purpose endpoints.

---

# Request Design

Requests should:

- Validate inputs
- Define required fields
- Support optional fields where appropriate
- Reject invalid data with meaningful errors

---

# Response Design

Responses should:

- Be deterministic
- Contain only relevant data
- Avoid unnecessary nesting
- Support future extensibility

---

# Pagination

Collections should support pagination when result sizes may become large.

Recommended metadata includes:

- totalCount
- page
- pageSize
- nextCursor

---

# Filtering

Filtering should be explicit, documented, and predictable.

---

# Sorting

Sorting should support stable ordering and clearly documented sort fields.

---

# Searching

Search behavior should define:

- searchable fields
- partial matching
- exact matching
- case sensitivity

---

# Idempotency

Operations intended to be safely retried should support idempotent behavior.

---

# Bulk Operations

Bulk requests should define:

- maximum batch size
- partial success behavior
- failure reporting
- transaction semantics

---

# Long-Running Operations

Asynchronous operations should expose execution status and completion mechanisms.

---

# Extensibility

API contracts should allow future fields without breaking existing consumers.