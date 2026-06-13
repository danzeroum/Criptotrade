"""Tests for AuditorAgent — covering reflection, refinement, security, quality."""
from __future__ import annotations

import pytest

from src.agents.auditor_agent import AuditorAgent


@pytest.fixture
def agent():
    return AuditorAgent()


# ── execute ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_invalid_input_raises(agent):
    """Line 23: validate_input(None) → ValueError."""
    with pytest.raises(ValueError, match="Invalid audit task"):
        await agent.execute(None)


@pytest.mark.asyncio
async def test_execute_empty_task_raises(agent):
    with pytest.raises(ValueError, match="Invalid audit task"):
        await agent.execute({})


@pytest.mark.asyncio
async def test_execute_clean_code_returns_success(agent):
    result = await agent.execute({"code": "x = 1 + 1"})
    assert result["success"] is True
    assert result["final"]["passed"] is True
    assert "confidence" in result


@pytest.mark.asyncio
async def test_execute_dangerous_code_issues_detected(agent):
    """Lines 47: check_security called when code present."""
    result = await agent.execute({"code": "eval('x')"})
    assert result["final"]["passed"] is False
    issues = result["final"]["issues"]
    assert any("eval" in i["pattern"] for i in issues)


# ── audit ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_with_metrics_warnings(agent):
    """Lines 49-50: check_quality called when metrics present."""
    result = await agent.audit({
        "metrics": {"complexity": 15, "coverage": 60},
    })
    assert len(result["warnings"]) == 2


@pytest.mark.asyncio
async def test_audit_no_code_no_issues(agent):
    result = await agent.audit({})
    assert result["issues"] == []
    assert result["passed"] is True


# ── check_security ────────────────────────────────────────────────────────────

def test_check_security_detects_exec(agent):
    """Lines 82-98: exec( pattern → critical issue."""
    issues = agent.check_security("exec('rm -rf /')")
    assert any(i["pattern"] == "exec(" for i in issues)
    assert all(i["severity"] == "critical" for i in issues)


def test_check_security_detects_multiple_patterns(agent):
    code = "import __import__; os.system('ls'); subprocess.run([])"
    issues = agent.check_security(code)
    patterns = {i["pattern"] for i in issues}
    assert "__import__" in patterns
    assert "os.system" in patterns
    assert "subprocess" in patterns


def test_check_security_clean_code_returns_empty(agent):
    assert agent.check_security("x = 1 + 2") == []


# ── check_quality ─────────────────────────────────────────────────────────────

def test_check_quality_high_complexity_warning(agent):
    """Line 103-110: complexity > 10 → warning."""
    warnings = agent.check_quality({"complexity": 20})
    assert len(warnings) == 1
    assert warnings[0]["metric"] == "complexity"


def test_check_quality_low_coverage_warning(agent):
    """Lines 112-119: coverage < 80 → warning."""
    warnings = agent.check_quality({"coverage": 50})
    assert len(warnings) == 1
    assert warnings[0]["metric"] == "coverage"


def test_check_quality_good_metrics_no_warnings(agent):
    assert agent.check_quality({"complexity": 5, "coverage": 90}) == []


# ── reflect_on_assessment ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reflect_missed_something_when_passed_low_confidence(agent):
    """Lines 63-64: passed=True, confidence<0.8 → missed_anything=True."""
    assessment = {"passed": True, "confidence": 0.6, "warnings": []}
    reflection = await agent.reflect_on_assessment(assessment)
    assert reflection["missed_anything"] is True
    assert any("edge" in s.lower() for s in reflection["suggestions"])


@pytest.mark.asyncio
async def test_reflect_too_strict_when_many_warnings(agent):
    """Lines 66-67: >5 warnings → too_strict=True."""
    assessment = {"passed": True, "confidence": 0.9, "warnings": [{}] * 6}
    reflection = await agent.reflect_on_assessment(assessment)
    assert reflection["too_strict"] is True


# ── refine_assessment ─────────────────────────────────────────────────────────

def test_refine_filters_non_critical_when_too_strict(agent):
    """Line 76: too_strict → only critical issues kept."""
    assessment = {
        "issues": [
            {"severity": "critical", "pattern": "eval("},
            {"severity": "warning", "pattern": "unused_var"},
        ],
        "warnings": [],
        "passed": False,
        "confidence": 0.7,
    }
    reflection = {"missed_anything": False, "too_strict": True, "suggestions": []}
    refined = agent.refine_assessment(assessment, reflection)
    assert all(i["severity"] == "critical" for i in refined["issues"])


def test_refine_adds_extra_checks_when_missed(agent):
    """Lines 73-74: missed_anything → additional_checks added, confidence capped at 0.75."""
    assessment = {"issues": [], "warnings": [], "passed": True, "confidence": 0.9}
    reflection = {"missed_anything": True, "too_strict": False, "suggestions": []}
    refined = agent.refine_assessment(assessment, reflection)
    assert "additional_checks" in refined
    assert refined["confidence"] <= 0.75


# ── validate_results / score_agent_result ─────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_results_all_pass(agent):
    """Lines 122-133: high-scoring results → approved."""
    results = [
        {"agent": "strategy", "success": True, "confidence": 0.9, "tested": True},
        {"agent": "risk", "success": True, "confidence": 0.85},
    ]
    outcome = await agent.validate_results(results)
    assert outcome["approved"] is True
    assert outcome["confidence"] >= 0.6


@pytest.mark.asyncio
async def test_validate_results_low_score_flagged(agent):
    """Line 130: score < 0.6 → issues listed."""
    results = [{"agent": "bad_agent", "success": False, "error": "fail"}]
    outcome = await agent.validate_results(results)
    assert outcome["approved"] is False
    assert any("bad_agent" in issue for issue in outcome["issues"])


def test_score_agent_result_all_bonuses(agent):
    """Lines 137-144: all bonuses give max score."""
    result = {"success": True, "confidence": 0.8, "tested": True}
    assert agent.score_agent_result(result) == pytest.approx(1.0)
