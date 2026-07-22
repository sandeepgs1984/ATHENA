# Component Design

## Name

Payment Processor

---

## Responsibilities

- Validate requests
- Process payments
- Publish events

---

## Dependencies

- Payment Gateway
- Notification Service

---

## Public Interface

processPayment()

refund()

status()

---

## Extension Points

- Fraud Detection
- Retry Policies