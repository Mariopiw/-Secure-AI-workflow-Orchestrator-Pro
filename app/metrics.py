from prometheus_client import Counter, Histogram

WORKFLOWS_CREATED = Counter(
    "workflow_created_total", "Created workflows", ["tenant"]
)
WORKFLOW_TRANSITIONS = Counter(
    "workflow_transition_total", "Workflow transitions", ["from_status", "to_status"]
)
WORKFLOW_FAILURES = Counter(
    "workflow_failure_total", "Workflow failures", ["stage"]
)
WEBHOOK_DELIVERIES = Counter(
    "webhook_delivery_total", "Webhook delivery results", ["result"]
)
WORKFLOW_DURATION = Histogram(
    "workflow_processing_seconds", "Workflow processing duration"
)
