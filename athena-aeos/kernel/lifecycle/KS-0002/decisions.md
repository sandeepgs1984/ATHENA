# Architectural Decisions

## ADR-0029

Every entity SHALL have exactly one lifecycle state.

---

## ADR-0030

Lifecycle transitions SHALL be validated before execution.

---

## ADR-0031

Every transition SHALL produce an immutable audit event.

---

## ADR-0032

The canonical lifecycle SHALL be shared across all AEOS frameworks.

---

## ADR-0033

Frameworks MAY extend lifecycle behavior but SHALL NOT redefine the canonical lifecycle.