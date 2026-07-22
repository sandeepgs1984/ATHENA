# Automation Principles

## Purpose

Automation improves repeatability, speed and engineering confidence.

Automation should solve problems—not create them.

---

# Engineering Principles

Automation should be:

- Reliable
- Fast
- Deterministic
- Maintainable
- Observable

---

# Candidate Selection

Automate:

- Regression suites
- Stable workflows
- High-frequency scenarios
- Critical business paths

Avoid automating:

- Frequently changing UI
- One-time validations
- Exploratory investigations
- Low-value scenarios

---

# Stable Automation

Automation should avoid:

- Arbitrary sleeps
- Random timing
- Shared mutable state
- Test dependencies

Prefer:

- Explicit waits
- Stable identifiers
- Isolated execution
- Independent data

---

# Parallel Execution

Suites should support parallel execution whenever possible.

Benefits:

- Faster feedback
- Better CI utilization
- Reduced verification time

---

# Retry Strategy

Retries should mitigate environmental instability—not hide defects.

Repeated failures require investigation.

---

# Metrics

Measure:

- Success rate
- Flaky rate
- Execution duration
- Maintenance effort
- Failure causes

---

# AI Guidance

Recommend automation only when long-term maintenance cost is justified by execution frequency and business value.