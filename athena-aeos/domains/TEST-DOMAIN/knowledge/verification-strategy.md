# Verification Strategy

## Purpose

Verification Strategy defines how an organization determines the appropriate level, type, and scope of verification for a software change.

The objective is to maximize confidence while minimizing unnecessary verification effort.

---

# Strategy Principles

An effective verification strategy should be:

- Risk-driven
- Incremental
- Repeatable
- Measurable
- Cost-effective
- Continuously improving

---

# Verification Decision Matrix

| Change Type | Recommended Verification |
|--------------|--------------------------|
| UI Change | Unit + UI + Accessibility |
| API Change | Unit + Contract + Integration |
| Database Change | Unit + Integration + Migration Validation |
| Security Feature | Unit + Integration + Security Testing |
| Performance Optimization | Unit + Performance + Regression |
| Infrastructure Change | Smoke + Integration + Production Validation |

---

# Verification Pyramid

Preferred investment:

1. Static Analysis
2. Unit Tests
3. Contract Tests
4. Integration Tests
5. End-to-End Tests
6. Exploratory Testing

Higher levels provide broader confidence but are slower and more expensive.

---

# Trade-offs

More testing increases confidence but also increases execution time and maintenance cost.

An optimal strategy balances:

- Risk
- Cost
- Execution speed
- Maintainability

---

# Anti-Patterns

Avoid:

- Testing every scenario at every layer
- Measuring quality solely by code coverage
- Duplicating the same verification across multiple levels
- Large brittle end-to-end suites
- Ignoring production telemetry

---

# AI Guidance

When recommending a verification strategy:

1. Assess business risk.
2. Determine impacted components.
3. Recommend the minimum verification required to achieve confidence.
4. Prefer lower-cost verification where appropriate.
5. Escalate to higher verification levels only when justified by risk.

The objective is confidence—not maximum test count.