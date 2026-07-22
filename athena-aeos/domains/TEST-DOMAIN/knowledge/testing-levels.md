# Testing Levels

## Purpose

Different testing levels validate different engineering concerns.

Selecting the correct level reduces execution time while maximizing confidence.

---

# Level 1 — Static Verification

Examples:

- Code review
- Linting
- Static analysis
- Architecture validation

Fastest and cheapest verification.

---

# Level 2 — Unit Testing

Verifies individual functions or components in isolation.

Characteristics:

- Fast
- Deterministic
- High signal
- Low maintenance cost

---

# Level 3 — Contract Testing

Ensures interfaces remain compatible.

Examples:

- REST APIs
- GraphQL
- Protobuf
- Event schemas

Useful for independently deployable services.

---

# Level 4 — Integration Testing

Validates interaction between collaborating components.

Examples:

- Database integration
- Service communication
- Third-party SDKs
- Message queues

---

# Level 5 — System Testing

Verifies the complete application.

Focus:

- End-to-end workflows
- Cross-module behavior
- Business scenarios

---

# Level 6 — Acceptance Testing

Confirms business expectations.

Often executed with product owners or stakeholders.

---

# Level Selection

Prefer the lowest verification level capable of detecting the defect.

Escalate only when additional confidence is required.

---

# AI Guidance

When recommending tests:

- Prefer unit over integration.
- Prefer contract over full end-to-end.
- Use system tests only for critical workflows.
- Avoid verifying the same behavior repeatedly across multiple levels.