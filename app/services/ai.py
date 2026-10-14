import json

import httpx

from app.core.config import settings


class RetryableAIError(RuntimeError):
    pass


class PermanentAIError(RuntimeError):
    pass


def mock_risk_review(description: str) -> tuple[int, str]:
    text = description.lower()
    score = 10
    reasons: list[str] = []
    rules = {
        "customer": 10,
        "personal data": 20,
        "credit": 25,
        "insurance": 15,
        "biometric": 30,
        "automated decision": 25,
        "medical": 25,
        "fraud": 15,
    }
    for phrase, points in rules.items():
        if phrase in text:
            score += points
            reasons.append(phrase)
    return min(score, 100), (", ".join(reasons) if reasons else "no elevated-risk term detected")


def ollama_risk_review(description: str) -> tuple[int, str]:
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ai_model,
                "stream": False,
                "format": "json",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a risk-triage component. You provide decision support only. "
                            "Return JSON with risk_score 0-100 and a short reason."
                        ),
                    },
                    {"role": "user", "content": description},
                ],
                "options": {"temperature": 0},
            },
            timeout=60.0,
        )
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise RetryableAIError(str(exc)) from exc

    if response.status_code == 429 or response.status_code >= 500:
        raise RetryableAIError(f"AI endpoint status {response.status_code}")
    if response.status_code >= 400:
        raise PermanentAIError(f"AI endpoint status {response.status_code}")

    try:
        parsed = json.loads(response.json()["message"]["content"])
        score = max(0, min(100, int(parsed["risk_score"])))
        reason = str(parsed["reason"])[:1000]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PermanentAIError("AI returned invalid structured output") from exc
    return score, reason


def review_risk(description: str) -> tuple[int, str]:
    if settings.ai_mode.lower() == "ollama":
        return ollama_risk_review(description)
    return mock_risk_review(description)
