# Security Notes

## Implemented controls

- JWT authentication with Argon2 password hashing
- Roles: submitter, approver, operator, admin
- tenant-scoped workflow queries
- four-eyes rule: creator cannot approve own request when enabled
- explicit workflow state machine
- row locking for approval/execution transitions
- idempotency key + canonical request hash
- HMAC-SHA256 webhook signatures
- webhook replay-time window
- inbound webhook event deduplication
- signed outbound webhook with stable event ID
- AI cannot perform authorization transitions
- dead-letter records for unrecoverable work
- separate safe retry vs uncertain execution reconciliation
- structured logs with request/workflow/task IDs
- Prometheus metrics

## Why `NEEDS_RECONCILIATION` exists

Imagine a worker calls a payment API successfully and then crashes before updating PostgreSQL.
Blind retry could charge twice. A real system needs a way to say:

> “The outcome is uncertain. Check durable evidence or the external provider before retrying.”

That is what reconciliation represents.

## Production additions

Before a real bank/insurer deployment add:

- enterprise OIDC / Entra ID / Keycloak
- MFA and conditional access
- stronger permission model / policy engine
- TLS and ideally mTLS for internal service calls
- cloud secret manager / KMS
- PostgreSQL encryption/backups/PITR
- Redis HA/replication or managed broker
- network segmentation
- rate limiting / abuse controls
- OpenTelemetry traces and centralized SIEM
- malware/data-validation controls for untrusted payloads
- formal retention/deletion policy
- partner-specific webhook keys and key rotation
- audit-log integrity controls
- disaster-recovery exercises
- SAST/SCA/container scanning
