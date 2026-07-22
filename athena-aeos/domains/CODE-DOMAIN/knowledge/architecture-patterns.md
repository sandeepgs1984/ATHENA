# Architecture Patterns

The Code Engineering Domain recognizes the following architectural patterns.

---

# Layered Architecture

Responsibilities are separated into distinct layers.

Typical layers include:

- Presentation
- Application
- Domain
- Infrastructure

Suitable for business applications with clear separation of concerns.

---

# Clean Architecture

Business rules remain independent of frameworks, databases, and UI technologies.

Core principles:

- Dependency inversion
- Independent business logic
- Testability
- Maintainability

---

# Hexagonal Architecture

Also known as Ports and Adapters.

Business logic communicates through interfaces, allowing infrastructure components to be replaced without impacting the domain.

---

# Event-Driven Architecture

Components communicate through published events rather than direct invocation.

Benefits include:

- Loose coupling
- Scalability
- Asynchronous processing

---

# Microservices

Systems are decomposed into independently deployable services.

Characteristics:

- Autonomous deployment
- Bounded contexts
- Independent scalability

---

# Modular Monolith

A single deployable application organized into strongly isolated modules.

Suitable when operational simplicity is preferred while maintaining modularity.

---

# Client–Server

Responsibilities are divided between service providers and consumers.

Commonly used for mobile, web, and desktop applications communicating with backend services.