# Module Design

## Purpose

Modules organize related functionality into independently understandable and maintainable units.

---

## Principles

- Clear ownership
- Stable boundaries
- High cohesion
- Minimal public surface
- Explicit dependencies

---

## Module Responsibilities

A module should own:

- Business capability
- Data ownership
- Internal implementation
- Public contract

---

## Avoid

- Shared internal state
- Cross-module implementation knowledge
- Utility dumping grounds

---

## AI Guidance

Recommend modules organized around business capabilities rather than technical layers whenever practical.