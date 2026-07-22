# Engineering Artifact Metadata

Every engineering artifact should provide:

| Field | Required |
|--------|----------|
| ID | Yes |
| Name | Yes |
| Version | Yes |
| Owner | Yes |
| Status | Yes |
| Domain | Yes |
| Created Date | Yes |
| Updated Date | Yes |
| Review Status | Yes |
| Tags | Optional |

## Example

```yaml
metadata:
  id: CODE-001
  name: Authentication Service
  version: 1.0.0
  owner: Platform Team
  status: Active
  domain: CODE-DOMAIN
  review: Approved
```