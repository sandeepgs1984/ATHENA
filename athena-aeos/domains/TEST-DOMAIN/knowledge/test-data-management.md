# Test Data Management

## Purpose

Reliable verification depends on reliable data.

Poor test data is one of the largest causes of unstable automation and inconsistent verification.

---

# Principles

Test data should be:

- Predictable
- Isolated
- Repeatable
- Secure
- Disposable

---

# Data Sources

## Synthetic Data

Preferred for most testing.

Benefits:

- Safe
- Repeatable
- Privacy compliant

---

## Masked Production Data

Useful when production realism is required.

Sensitive information shall be anonymized.

---

## Seed Data

Predefined datasets created before execution.

Suitable for automated regression.

---

## Generated Data

Created dynamically during execution.

Useful for independent tests.

---

# Lifecycle

Create

↓

Use

↓

Validate

↓

Dispose

---

# Isolation

Tests should never depend on shared mutable data.

Each execution should be independently reproducible.

---

# Security

Never expose:

- Passwords
- Secrets
- Personal information
- Financial records

Sensitive information should always be masked or synthesized.

---

# AI Guidance

When generating verification scenarios:

- Prefer synthetic data.
- Reuse fixtures only when appropriate.
- Isolate every test.
- Minimize environmental dependencies.