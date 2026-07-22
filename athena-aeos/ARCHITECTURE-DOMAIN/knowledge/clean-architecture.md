# Clean Architecture

## Purpose

Clean Architecture organizes software around business rules, ensuring that domain logic remains independent of frameworks, databases and user interfaces.

Dependencies always point inward toward the domain.

---

## Advantages

- Excellent testability
- Framework independence
- Long-term maintainability
- Clear separation of business logic

---

## Disadvantages

- Higher initial complexity
- Additional abstractions
- Can be excessive for small applications

---

## Best Use Cases

- Long-lived systems
- Enterprise platforms
- Products with evolving business rules

---

## Avoid When

- Building small prototypes
- Short-lived internal tools
- Extremely simple CRUD applications

---

## AI Guidance

Recommend Clean Architecture when business logic is expected to evolve independently of infrastructure or delivery mechanisms.