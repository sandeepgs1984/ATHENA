# Test Environments

## Purpose

A verification environment provides the infrastructure required to execute tests with predictable and reproducible results.

Environment quality directly influences verification quality.

---

# Environment Principles

Environments should be:

- Stable
- Reproducible
- Isolated
- Observable
- Representative of production

---

# Common Environments

## Development

Used for rapid local validation.

Characteristics:

- Fast feedback
- Frequent changes
- Limited stability

---

## Integration

Validates interactions between multiple components.

Used for:

- API integration
- Database validation
- Third-party services

---

## Staging

Production-like environment used before release.

Should closely match:

- Infrastructure
- Configuration
- Network topology
- Security policies

---

## Production

Final validation occurs through monitoring and controlled rollout strategies.

Examples:

- Smoke verification
- Canary deployments
- Feature flags

---

# Environment Drift

Differences between staging and production should be minimized and documented.

---

# AI Guidance

Recommend the lowest environment capable of providing the required confidence while minimizing execution cost.