# Language Guidelines

## Purpose

This document defines universal engineering guidelines that apply regardless of the programming language.

Language-specific syntax and framework guidance belong to dedicated language knowledge packs.

---

# General Principles

## Prefer Explicitness

Code should clearly communicate intent.

---

## Prefer Immutability

Immutable data structures reduce unintended side effects and simplify reasoning.

---

## Minimize Shared State

Shared mutable state should be avoided whenever possible.

---

## Dependency Injection

Dependencies should be injected rather than created internally.

---

## Composition Over Inheritance

Prefer composing behavior from smaller components instead of deep inheritance hierarchies.

---

## Interface-Based Design

Depend on abstractions rather than concrete implementations.

---

## Defensive Programming

Validate external inputs.

Assume external systems may fail.

---

## Error Handling

Errors should contain:

- Cause
- Context
- Recovery information (where applicable)

---

## Concurrency

Shared resources must be synchronized appropriately.

Avoid blocking operations on latency-sensitive execution paths.

---

## Performance

Optimize only after measuring.

Avoid premature optimization.

---

## Security

Never expose secrets.

Validate all external inputs.

Use secure defaults.