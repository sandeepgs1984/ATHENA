# Architecture Decision Framework

## Purpose

Architecture decisions should be systematic, transparent and repeatable.

The Architecture Decision Framework provides a structured process for selecting appropriate architectural approaches.

---

# Decision Flow

Business Problem

↓

Business Goals

↓

Constraints

↓

Quality Attributes

↓

Candidate Architectures

↓

Trade-off Analysis

↓

Risk Assessment

↓

Decision

↓

Architecture Review

↓

ADR Publication

---

# Step 1 — Understand the Problem

Define:

- Business capability
- Functional requirements
- Non-functional requirements
- Expected lifespan
- Scale expectations

Avoid designing solutions before understanding the problem.

---

# Step 2 — Identify Constraints

Examples:

- Budget
- Timeline
- Team expertise
- Regulatory requirements
- Existing systems
- Operational maturity

Constraints shape viable architectural options.

---

# Step 3 — Prioritize Quality Attributes

Common quality attributes include:

- Performance
- Scalability
- Availability
- Reliability
- Security
- Maintainability
- Extensibility
- Cost efficiency

Trade-offs are inevitable; prioritize explicitly.

---

# Step 4 — Evaluate Candidate Architectures

For each option, assess:

- Benefits
- Drawbacks
- Complexity
- Operational cost
- Team familiarity
- Long-term maintainability

Document why alternatives were accepted or rejected.

---

# Step 5 — Assess Risks

Consider:

- Technical risks
- Delivery risks
- Operational risks
- Organizational risks
- Vendor lock-in
- Future scalability

Mitigation plans should accompany significant risks.

---

# Step 6 — Record the Decision

Every major architectural decision should produce an ADR containing:

- Context
- Decision
- Alternatives
- Consequences
- Review date

Architecture without documented rationale becomes difficult to evolve.

---

# Common Anti-Patterns

Avoid:

- Architecture driven by trends
- Premature microservices
- Gold-plated designs
- Ignoring operational complexity
- Optimizing every quality attribute equally
- Undocumented architectural decisions

---

# AI Guidance

When recommending an architecture:

1. Understand the business problem.
2. Identify constraints.
3. Rank quality attributes.
4. Compare viable architectural styles.
5. Explain trade-offs.
6. Recommend the simplest architecture that satisfies current and foreseeable requirements.
7. Document the rationale as an Architecture Decision Record (ADR).