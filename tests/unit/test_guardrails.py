from src.safety.guardrails import GuardrailSystem


def test_guardrail_position_size_limit():
    guardrails = GuardrailSystem()
    order = {"position_size_pct": 10.0}
    passed, violations = guardrails.validate_order(order)
    assert not passed
    assert any("exceeds" in violation for violation in violations)


def test_guardrail_requires_stop_loss():
    guardrails = GuardrailSystem()
    order = {"position_size_pct": 2.0, "action": "BUY", "entry_price": 100.0}
    passed, violations = guardrails.validate_order(order)
    assert not passed
    assert "Stop loss is mandatory" in violations


def test_guardrail_risk_reward_ratio():
    guardrails = GuardrailSystem()
    order = {
        "position_size_pct": 2.0,
        "action": "BUY",
        "entry_price": 100.0,
        "stop_loss": 99.5,
        "take_profit": 101.0,
    }
    passed, violations = guardrails.validate_order(order)
    assert not passed
    assert any("Risk-reward" in violation for violation in violations)
