# RC-0003 — Layer Dependency Matrix

## Overview

The Layer Dependency Matrix defines the permitted dependencies between architectural layers.

Its purpose is to preserve the layered architecture by preventing invalid or circular dependencies.

---

## Purpose

The matrix establishes a repository-wide contract for layer interactions.

Every new specification should conform to these dependency rules unless an approved ADR explicitly states otherwise.

---

## Scope

Applies to every architectural layer within AEOS.