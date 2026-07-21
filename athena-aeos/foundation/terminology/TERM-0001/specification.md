# TERM-0001 — Canonical Terminology

| Property | Value |
|----------|-------|
| ID | TERM-0001 |
| Version | 1.0.0 |
| Status | Approved |
| Category | Foundation Specification |
| Owner | Chief Systems Architect |

---

# Purpose

This specification defines the official terminology used throughout AEOS.

Every specification SHALL use these definitions consistently.

---

# Core Terms

## Engineering

The governed process of transforming requirements into validated software through architecture, implementation, verification, and continuous evolution.

---

## Knowledge

Structured engineering information that retains value independently of implementation.

Examples:

- Specifications
- Architecture
- ADRs
- Lessons Learned
- Design Decisions

---

## Entity

The fundamental identifiable object within AEOS.

Every Entity possesses:

- Identity
- Type
- Metadata
- Lifecycle
- Relationships
- Version

Examples:

- Role
- Capability
- Workflow
- Policy
- Project
- Artifact

---

## Artifact

A tangible output produced by engineering activities.

Examples:

- Source Code
- Specifications
- Documents
- Tests
- Architecture Diagrams
- Release Notes

---

## Specification

A normative document defining expected behavior, structure, constraints, or governance.

Specifications govern implementations.

---

## Architecture

The structural organization of engineering components and their interactions.

Architecture defines implementation.

---

## Capability

A reusable engineering function that performs a well-defined responsibility.

Examples:

- Code Review
- API Design
- Test Generation
- Security Analysis

---

## Role

An engineering responsibility assigned to a human or autonomous participant.

Examples:

- Principal Engineer
- Security Engineer
- QA Engineer
- Documentation Engineer

---

## Workflow

An ordered sequence of engineering activities executed to achieve a specific objective.

---

## Policy

A governance rule constraining engineering behavior.

Policies are enforceable.

---

## Runtime

The execution environment responsible for performing engineering work.

Examples:

- Cursor
- Claude
- Codex
- Gemini

---

## Project Pack

A collection of specifications, capabilities, templates, workflows and configurations tailored for a particular software project.

---

## Knowledge Graph

A structured network of interconnected engineering entities and relationships.

---

## Review

A formal engineering evaluation performed prior to approval.

---

## Approval

Formal acceptance of an engineering artifact.

Approval authorizes progression to the next lifecycle stage.

---

## Lifecycle

The sequence of states through which an engineering entity evolves.

Example:

Draft

↓

Review

↓

Approved

↓

Active

↓

Deprecated

↓

Retired

---

# Naming Rules

Specifications SHALL use consistent terminology.

Incorrect:

Agent

Correct:

Role

---

Incorrect:

Tool

Correct:

Runtime

---

Incorrect:

Feature

Correct:

Capability

unless referring to project functionality.

---

# Conformance

Future specifications SHALL use the terminology defined in this document.

Introduction of new terminology requires review and approval.