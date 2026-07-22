# Design Patterns

## Purpose

This document defines reusable software design patterns recommended across engineering projects.

The selection focuses on patterns that improve maintainability, extensibility, and testability.

---

# Creational Patterns

## Factory

Encapsulates object creation.

Use when object construction depends on runtime conditions or implementation details.

---

## Builder

Separates object construction from representation.

Use for complex immutable objects with many optional properties.

---

## Singleton

Ensures a single instance exists.

Use sparingly and only for truly shared application-wide resources.

---

# Structural Patterns

## Adapter

Converts one interface into another.

Useful when integrating legacy or third-party components.

---

## Facade

Provides a simplified interface over a complex subsystem.

---

## Decorator

Adds behavior without modifying the original implementation.

Preferred over subclassing when extending functionality dynamically.

---

## Composite

Represents hierarchical tree structures while treating individual and grouped objects uniformly.

---

# Behavioral Patterns

## Strategy

Encapsulates interchangeable algorithms.

Preferred over conditional logic for runtime behavior selection.

---

## Observer

Supports event-driven communication between components.

Subscribers react to published state changes without tight coupling.

---

## Command

Encapsulates requests as executable objects.

Useful for undo/redo, task queues, and asynchronous execution.

---

## State

Represents object behavior through explicit states.

Avoids deeply nested conditional logic.

---

## Template Method

Defines a common algorithm while allowing subclasses to customize individual steps.

---

# Pattern Selection Principles

Choose the simplest pattern that satisfies the engineering requirements.

Avoid introducing patterns solely because they are available.

Patterns SHALL improve:

- Maintainability
- Readability
- Testability
- Extensibility