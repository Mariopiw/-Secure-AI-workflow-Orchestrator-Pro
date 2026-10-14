# Control Mapping

This file maps engineering mechanisms to common regulated-AI control objectives. It is an
engineering aid, not a claim of legal compliance.

| Control objective | Project mechanism | Evidence |
|---|---|---|
| Accountability | immutable-style workflow events + approvals | `workflow_events`, `approvals` |
| Human oversight | explicit WAITING_APPROVAL state | `/workflows/{id}/decision` |
| Separation of duties | four-eyes creator/approver check | `FOUR_EYES_REQUIRED` |
| Traceability | request/workflow/task IDs + structured logs | JSON logs, event history |
| Least privilege | submitter/approver/operator roles | JWT RBAC dependencies |
| Reliable processing | Celery late ack + retry/backoff | `celery_app.py`, `tasks.py` |
| Duplicate protection | idempotency key + request hash | workflow unique constraint |
| Integration integrity | HMAC webhooks + timestamp | `security.py`, `webhooks.py` |
| Event reliability | transactional outbox | `outbox_events` |
| Failure visibility | dead letters + metrics | `dead_letters`, `/metrics` |
| Safe recovery | FAILED vs NEEDS_RECONCILIATION | scheduler + operator API |
| AI bounded authority | model only emits risk evidence | `services/ai.py` |

## NIST AI RMF-style framing

- **Govern:** roles, approval responsibilities, event history.
- **Map:** workflow type, business context, risk score/reason.
- **Measure:** failures, webhook results, transitions, latency/operational metrics.
- **Manage:** retries, dead letters, reconciliation, human authorization.
