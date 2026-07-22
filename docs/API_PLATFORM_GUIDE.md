# ATHENA API Platform Infrastructure Guide

This guide describes the production-grade infrastructure, observability, error-handling conventions, versioning policy, and diagnostic endpoints established in Phase 8.5.

---

## 1. API Platform Module Architecture
All platform diagnostics, capabilities metadata, version indicators, and request tracking reside under:
`src/athena/api/platform/`

The module is decoupled from the business domain logic:
```
HTTP Request -> Router -> Service -> Provider -> Domain Engine
```

---

## 2. Health & Diagnostics Endpoints
Production deployment requires three dedicated diagnostic endpoints mounted at the API root:

### `GET /health`
Provides detailed diagnostic state aggregating all components checks:
```json
{
  "status": "UP",
  "timestamp": "2026-07-22T12:00:00Z",
  "version": "1.0.0",
  "checks": [
    {
      "name": "database",
      "status": "UP",
      "detail": "SQLite active connection"
    }
  ]
}
```

### `GET /health/live`
Process-level liveness ping used by container engines (e.g. k8s livenessProbe). Always returns `200 OK` if the Python process is alive.

### `GET /health/ready`
Traffic readiness check. If database or system configuration state is stale or unready, returns `status: DOWN` (HTTP 503).

---

## 3. Versioning Policy
All version metadata is provided through the `BuildInfoProvider` protocol, enabling future CI/CD processes to write/inject parameters dynamically.

### `GET /api/version`
Exposes the version metadata block:
- **app_name**: Application identity ("ATHENA")
- **semver**: Semantic version (e.g. "1.0.0")
- **api_version**: Current active API version protocol ("v1")
- **build_number**: Unique CI/CD compile serial
- **commit_hash**: Git revision SHA
- **environment**: Deploy stage ("production", "test", "development")
- **runtime_info**: System details (Python compiler, machine CPU, platform OS)

---

## 4. Header Specification
Every API request and response is decorated with platform-standard tracing and metadata headers:

| Header Name | Type | Purpose |
|-------------|------|---------|
| `X-Request-ID` | Out / In | Unique identifier generated (UUID4) for tracing this request lifecycle. |
| `X-Correlation-ID` | Out / In | Correlation tracking identifier passed down through microservices or logs. |
| `X-API-Version` | Out | Current target API protocol version (e.g. `v1`). |
| `Deprecation` | Out | Optional. Indicates that the endpoint is deprecated. |
| `Sunset` | Out | Optional. Indicates the timestamp when the endpoint will be removed. |

---

## 5. Unified Problem Details (RFC 9457)
All business and runtime errors are mapped to standardized RFC 9457 payloads, guaranteeing that no internal stack traces or database connection strings leak to client interfaces.

### Error Schema Invariants
Every error response exposes:
1. `type`: Error category URI reference.
2. `title`: Human-readable error category summary.
3. `status`: HTTP status code mapping.
4. `detail`: Specific explanation of this fault instance.
5. `instance`: URI path of request.
6. `request_id`: Request ID tracing token.
7. `correlation_id`: Correlation tracing token.
8. `timestamp`: ISO-8601 timestamp.
9. `invalid_params`: Optional list of validation details (present for HTTP 422).

Example Validation Error:
```json
{
  "type": "https://athena.internal/errors/validation-error",
  "title": "Validation Failed",
  "status": 422,
  "detail": "body -> source -> artifact_id: Field required",
  "instance": "/api/v1/exports",
  "request_id": "req-uuid-1234",
  "correlation_id": "corr-uuid-1234",
  "timestamp": "2026-07-22T12:00:00Z",
  "invalid_params": [
    {
      "type": "missing",
      "loc": ["body", "source", "artifact_id"],
      "msg": "Field required"
    }
  ]
}
```

---

## 6. Metadata & Capability Discovery
Discovery endpoints allow Desktop and UI clients to initialize metadata matrices, features, and active capabilities.

### `GET /api/meta`
Active profile name, version compatibility, and registered API module listings.

### `GET /api/features`
Active system profile feature flag statuses.

### `GET /api/capabilities`
Structured registry listing active and experimental capabilities:
- **name**: Identity slug
- **version**: Semantic version
- **category**: Category class ("INGESTION", "INTELLIGENCE", "SIMULATION", etc.)
- **description**: Clear functional capability context
- **enabled**: Status flag
- **experimental**: Dev lifecycle flag

### `GET /api/info`
Consolidated startup payload combining version info, profile meta, feature flag maps, and capabilities registries. This is the preferred endpoint for Athena desktop initialization.
