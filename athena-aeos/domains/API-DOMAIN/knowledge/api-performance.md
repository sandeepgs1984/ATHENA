# API Performance

## Purpose

Define engineering practices that improve API responsiveness, scalability and efficiency.

---

# Response Time

APIs should define measurable latency objectives.

Performance targets should be documented and continuously monitored.

---

# Payload Size

Responses should include only required information.

Avoid unnecessary fields and deeply nested structures.

---

# Pagination

Large collections should support pagination.

Cursor-based pagination is recommended for continuously changing datasets.

---

# Caching

Caching strategies may include:

- ETags
- Cache-Control
- Conditional Requests
- CDN Caching

Caching policies should be documented.

---

# Compression

Large payloads should support transport compression.

---

# Batch Operations

Support batch processing when multiple requests are commonly executed together.

---

# Asynchronous Processing

Long-running operations should return immediately and provide status tracking.

---

# Timeouts

Define timeout expectations for:

- Client
- Gateway
- Service
- Downstream dependencies

---

# Resilience

APIs should support:

- Retries
- Exponential backoff
- Circuit breakers
- Graceful degradation

---

# Observability

Collect:

- Request latency
- Error rates
- Throughput
- Availability
- Saturation

Performance metrics should feed continuous optimization efforts.