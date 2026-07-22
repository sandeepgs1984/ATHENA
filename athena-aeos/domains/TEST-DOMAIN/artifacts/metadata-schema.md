# Verification Artifact Metadata

Every verification artifact should contain:

| Field | Required |
|--------|----------|
| ID | Yes |
| Name | Yes |
| Owner | Yes |
| Version | Yes |
| Status | Yes |
| Verification Level | Yes |
| Risk | Yes |
| Related Requirement | Yes |
| Review Status | Yes |
| Tags | Optional |

## Example

```yaml
metadata:
  id: TEST-001
  name: Login Verification
  version: 1.0.0
  owner: Platform QA
  verification_level: Integration
  risk: High
  status: Approved
```