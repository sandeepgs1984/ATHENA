# Modular Monolith

## Purpose

A Modular Monolith keeps deployment as a single application while enforcing strict module boundaries internally.

Modules communicate through explicit contracts rather than unrestricted code access.

---

## Advantages

- Simple deployment
- Lower operational complexity
- High performance
- Easier debugging
- Incremental evolution

---

## Disadvantages

- Requires disciplined modularization
- Risk of boundary erosion
- Independent deployment is not possible

---

## Best Use Cases

- Startups
- Growing SaaS products
- Products with a single engineering team
- Early-stage platforms

---

## Avoid When

- Teams require fully independent deployments
- Organizational scale demands autonomous ownership

---

## AI Guidance

Default to a Modular Monolith unless clear business or organizational constraints justify distributed services.