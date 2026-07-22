# Documentation Metadata Schema

Every documentation artifact SHALL include the following metadata.

| Field | Required | Description |
|--------|----------|-------------|
| ID | Yes | Unique document identifier |
| Title | Yes | Document title |
| Version | Yes | Semantic version |
| Status | Yes | Draft, Review, Approved, Deprecated |
| Owner | Yes | Responsible individual or team |
| Created Date | Yes | Initial creation date |
| Last Updated | Yes | Most recent modification date |
| Reviewer | Yes | Engineering reviewer |
| Domain | Yes | Owning engineering domain |
| Tags | Optional | Searchable keywords |
| Dependencies | Optional | Related documents |
| References | Optional | External references |

---

## Example

```yaml
metadata:
  id: DOC-0001
  title: Authentication Service Design
  version: 1.2.0
  status: Approved
  owner: Platform Team
  created: 2026-07-22
  updated: 2026-07-25
  reviewer: Architecture Board
  domain: DOC-DOMAIN
  tags:
    - authentication
    - security
    - api
```