# Resilience Patterns

## Purpose

Resilience enables systems to continue operating despite failures.

Failure is expected.

Architecture should minimize user impact rather than assume perfect infrastructure.

---

## Core Patterns

### Retry

Retry transient failures using bounded retries with exponential backoff.

---

### Timeout

Prevent resource exhaustion by limiting waiting time.

---

### Circuit Breaker

Temporarily stop requests to unhealthy dependencies.

---

### Bulkhead

Isolate failures between independent resources.

---

### Fallback

Provide degraded functionality when dependencies fail.

---

### Health Checks

Expose service readiness and liveness.

---

### Graceful Degradation

Maintain essential functionality while temporarily disabling non-critical features.

---

## Anti-Patterns

Avoid:

- Infinite retries
- Cascading failures
- Shared failure domains
- Hidden dependency failures

---

## AI Guidance

Recommend resilience patterns based on dependency criticality, latency sensitivity and business impact.