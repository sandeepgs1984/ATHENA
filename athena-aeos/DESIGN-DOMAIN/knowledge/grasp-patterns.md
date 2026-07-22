# GRASP Patterns

## Purpose

GRASP (General Responsibility Assignment Software Patterns) provides guidelines for assigning responsibilities effectively.

---

## Core Patterns

### Information Expert

Assign responsibility to the component with the necessary information.

---

### Creator

Assign object creation to the component that aggregates or closely uses the created object.

---

### Controller

Handle system events through dedicated controllers rather than UI or infrastructure components.

---

### Low Coupling

Reduce unnecessary dependencies.

---

### High Cohesion

Group related responsibilities together.

---

### Polymorphism

Replace conditional behavior with polymorphic implementations where appropriate.

---

### Pure Fabrication

Introduce a supporting class when it improves cohesion or reduces coupling.

---

### Indirection

Use intermediaries only when they meaningfully reduce coupling.

---

### Protected Variations

Isolate unstable areas behind stable interfaces.

---

## AI Guidance

Use GRASP to assign responsibilities based on information ownership and collaboration rather than arbitrary layering.