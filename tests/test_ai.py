from app.services.ai import mock_risk_review


def test_regulated_terms_raise_mock_risk_score():
    score, reason = mock_risk_review(
        "Use customer personal data for an automated decision about credit eligibility."
    )
    assert score >= 60
    assert "credit" in reason
