# Event-Driven Architecture

## Purpose

Event-Driven Architecture enables components to communicate through events instead of direct synchronous requests.

Producers publish events without knowledge of consumers.

---

## Advantages

- Loose coupling
- High scalability
- Asynchronous workflows
- Independent evolution

---

## Disadvantages

- Eventual consistency
- Debugging complexity
- Event versioning
- Operational visibility requirements

---

## Best Use Cases

- Business workflows
- Notifications
- Streaming systems
- Financial processing
- Analytics

---

## Avoid When

- Immediate consistency is mandatory
- Workflows are simple and synchronous

---

## AI Guidance

Recommend Event-Driven Architecture when decoupling, scalability and asynchronous processing outweigh the complexity of distributed coordination.