# Interview Q&A

## 1. Why do you need a workflow orchestrator?
Because regulated business processes span multiple slow/retryable steps, external systems,
human decisions, and failure modes. A durable workflow makes state and recovery explicit.

## 2. Why not execute everything inside the FastAPI request?
The API should validate and persist intent quickly. Slow AI or integration work belongs on
independently scalable workers so API latency and worker throughput are decoupled.

## 3. Why Celery?
It provides mature distributed workers, acknowledgement semantics, retries, scheduling,
routing, and monitoring. It is a strong 80/20 choice for this portfolio architecture.

## 4. Why Redis?
Redis is a stable Celery broker and easy to operate locally. I treat it as transport, not the
durable business database. For enterprise requirements I would also evaluate RabbitMQ or SQS.

## 5. Why PostgreSQL as source of truth?
Workflow state, approvals, effects, and audit history require durable relational consistency.
They should remain reconstructable even if the broker is lost.

## 6. What is idempotency?
Repeating the same logical command does not create a duplicate business effect. The API stores
an Idempotency-Key and request hash; same key/same body returns the original object, while same
key/different body is rejected.

## 7. Why hash the request?
It distinguishes a legitimate replay from accidental or malicious reuse of an idempotency key
for a different operation.

## 8. What delivery guarantee do you design for?
At least once. A worker can crash and a task can be redelivered, so business effects must be
idempotent or explicitly reconciled.

## 9. Why `task_acks_late=True`?
The message is acknowledged after execution. If the worker dies mid-task, the message can be
redelivered. That improves resilience but makes idempotency mandatory.

## 10. Do you guarantee exactly-once execution?
No. Exactly-once across a broker, database, and arbitrary remote services is not something a
Celery flag can guarantee. I use idempotent effects, stable event IDs, unique constraints, and
reconciliation.

## 11. What is the transactional outbox pattern?
Business state and an event-to-publish are committed atomically in one database transaction.
A separate dispatcher publishes the durable outbox row later, preventing a database/message
dual-write gap.

## 12. Why `FOR UPDATE SKIP LOCKED`?
Multiple outbox dispatcher instances can consume different pending rows concurrently without
blocking each other. It is appropriate for queue-like tables, not general consistent reads.

## 13. What is exponential backoff?
Retry delays increase after repeated transient failures, reducing pressure on an unhealthy
dependency. Jitter should be added at larger scale to avoid synchronized retry storms.

## 14. Which webhook failures are retryable?
Timeouts, connection failures, 429, and most 5xx responses. Most 4xx responses are permanent
request/configuration errors and should go to dead-letter rather than be retried forever.

## 15. Why sign webhooks?
HMAC lets the receiver verify message integrity and knowledge of a shared secret. A timestamp
is included to support replay-window checks.

## 16. Why also send an event ID?
Webhook delivery can repeat after timeouts. A stable event ID lets the receiving system
idempotently deduplicate the logical event.

## 17. Why human approval after AI review?
The AI output is probabilistic evidence, not authorization. An authenticated human/policy
control owns the high-impact transition.

## 18. What is the four-eyes principle?
The person who created a high-impact request cannot be the only person approving it. This
separates duties and reduces fraud/error risk.

## 19. Why use a state machine?
It encodes legal transitions. WAITING_APPROVAL cannot jump to COMPLETED, for example. This
turns process rules into deterministic software rather than conventions.

## 20. Why row-lock workflows before decisions?
Two approvers or workers can race. `SELECT ... FOR UPDATE` serializes the critical transition
so only one transaction changes that workflow state at a time.

## 21. FAILED vs NEEDS_RECONCILIATION?
FAILED means a pre-execution failure is understood and safe to retry. NEEDS_RECONCILIATION
means an external/business effect may have occurred and an operator must establish truth before
another attempt.

## 22. Why dead letters?
Repeated/permanent failures must remain visible and inspectable rather than disappear. Dead
letters support operations, root-cause analysis, and controlled replay.

## 23. What would you monitor?
Workflow throughput, end-to-end duration, time waiting for approval, worker retries, failure
rates, dead-letter volume, stuck workflow count, webhook latency/success, queue age/depth, and
dependency health.

## 24. When would you choose Temporal instead?
For very long-lived workflows where durable timers, signals, workflow history, replay, and
complex orchestration are first-class requirements. Celery is simpler for this project's
80/20 reliability target.

## 25. Explain the project in 30 seconds.
I built a multi-tenant secure AI workflow orchestrator using FastAPI, PostgreSQL, Redis and
Celery. API commands are idempotent, workflow transitions are explicit and row-locked, AI only
performs risk triage, and a separate approver authorizes execution. Business effects are
idempotent, completion notifications use a transactional outbox and signed retryable webhooks,
and uncertain execution failures move to operator reconciliation rather than blind retry. I
also added scheduled recovery, dead letters, structured logging, Prometheus metrics, Alembic
migrations, tests and CI.
