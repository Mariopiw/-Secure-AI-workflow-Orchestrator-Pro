import os
import time
import httpx

BASE = os.getenv("BASE_URL", "http://localhost:8000")


def login(username, password):
    r = httpx.post(f"{BASE}/auth/token", data={"username": username, "password": password}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]

submitter = login("submitter", os.getenv("SUBMITTER_PASSWORD", "change-submit-password"))
approver = login("approver", os.getenv("APPROVER_PASSWORD", "change-approve-password"))
headers = {"Authorization": f"Bearer {submitter}", "Idempotency-Key": "smoke-2026-0001"}
payload = {
    "case_reference": "SMOKE-001",
    "description": "Use customer personal data to support an automated credit decision.",
    "callback_url": "http://api:8000/webhooks/demo-partner",
}
r = httpx.post(f"{BASE}/workflows", headers=headers, json=payload, timeout=20)
r.raise_for_status()
workflow = r.json()
public_id = workflow["public_id"]
print("created", public_id)

for _ in range(30):
    time.sleep(1)
    r = httpx.get(f"{BASE}/workflows/{public_id}", headers={"Authorization": f"Bearer {submitter}"})
    r.raise_for_status()
    if r.json()["status"] == "WAITING_APPROVAL":
        break
else:
    raise SystemExit("workflow did not reach approval")

r = httpx.post(
    f"{BASE}/workflows/{public_id}/decision",
    headers={"Authorization": f"Bearer {approver}"},
    json={"decision": "APPROVE", "comment": "smoke test"},
    timeout=20,
)
r.raise_for_status()
print("approved")

for _ in range(30):
    time.sleep(1)
    r = httpx.get(f"{BASE}/workflows/{public_id}", headers={"Authorization": f"Bearer {submitter}"})
    r.raise_for_status()
    state = r.json()["status"]
    if state == "COMPLETED":
        print("completed")
        break
else:
    raise SystemExit(f"workflow did not complete; last={state}")
