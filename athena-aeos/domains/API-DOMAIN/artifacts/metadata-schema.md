# API Artifact Metadata

Every API engineering artifact should include:

| Field | Required |
|---------|----------|
| ID | Yes |
| Name | Yes |
| Version | Yes |
| Owner | Yes |
| Protocol | Yes |
| Status | Yes |
| Visibility | Yes |
| Lifecycle Stage | Yes |
| Review Status | Yes |
| Tags | Optional |

## Example

```yaml
metadata:
  id: API-001
  name: Customer Service API
  version: 1.0.0
  protocol: OpenAPI
  owner: Platform Team
  status: Published
  review: Approved
```