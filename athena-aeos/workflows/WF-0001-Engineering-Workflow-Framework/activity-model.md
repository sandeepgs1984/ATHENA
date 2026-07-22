# Activity Model

An Activity is the smallest reusable execution unit within a Workflow.

---

## Responsibilities

An Activity SHALL:

- Perform one responsibility
- Consume workflow context
- Produce output for the next activity
- Report execution status

---

## Activity Properties

- Identifier
- Name
- Purpose
- Inputs
- Outputs
- Dependencies
- Execution Rules

---

## Rules

Activities SHALL:

- Be reusable
- Be independently testable
- Have single responsibility
- Not execute outside a Workflow