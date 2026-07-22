# Architecture Artifact Metadata

Every architecture artifact should contain:

| Field | Required |
|---------|----------|
| ID | Yes |
| Name | Yes |
| Owner | Yes |
| Version | Yes |
| Status | Yes |
| Architecture Style | Yes |
| Quality Attributes | Yes |
| Review Status | Yes |
| ADR Reference | Optional |

## Example

```yaml
metadata:
  id: ARCH-001
  name: Payments Platform
  architecture_style: Modular Monolith
  owner: Platform Team
  version: 1.0
  review: Approved
```