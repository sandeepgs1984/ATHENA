# API Security

## Purpose

This document defines universal engineering principles for securing APIs regardless of implementation technology.

Security SHALL be considered during API design rather than added after implementation.

---

# Security Principles

## AS-001 Secure by Default

APIs shall deny access unless explicitly authorized.

---

## AS-002 Least Privilege

Clients should receive only the permissions required for their intended operations.

---

## AS-003 Authentication

Every protected API shall define an approved authentication mechanism.

Examples include:

- OAuth 2.0
- OpenID Connect
- JWT
- API Keys
- Mutual TLS

---

## AS-004 Authorization

Authentication identifies a client.

Authorization determines what that client may access.

Authorization decisions shall be enforced for every protected resource.

---

## AS-005 Transport Security

Sensitive APIs shall require encrypted communication.

HTTPS/TLS is mandatory for production environments.

---

## AS-006 Input Validation

Validate:

- Parameters
- Headers
- Query values
- Request bodies
- Uploaded files

Reject malformed input immediately.

---

## AS-007 Output Protection

Never expose:

- Internal stack traces
- Database schema
- Secrets
- Tokens
- Passwords
- Internal identifiers

---

## AS-008 Secrets

Secrets shall never appear in:

- Source code
- Logs
- API responses
- Client applications

---

## AS-009 Rate Limiting

Public APIs should define:

- Requests per minute
- Burst limits
- Retry behavior

---

## AS-010 Auditability

Security-relevant operations should generate audit events.

Examples:

- Login
- Token issuance
- Permission changes
- Administrative actions