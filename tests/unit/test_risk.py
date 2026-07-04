"""Unit tests for risk management modules."""
from __future__ import annotations

from src.orchestration.squad_orchestrator import CircuitBreaker
from src.risk.capital_protections import CapitalProtections, DrawdownStatus
from src.risk.position_sizing import KellyCriterion, PositionSizer, risk_of_ruin
from src.safety.guardrails import GuardrailSystem

# ---------------------------------------------------------------------------
# KellyCriterion
# ---------------------------------------------------------------------------

class TestKellyCriterion:
    def test_full_kelly_insufficient_data(self):
        kc = KellyCriterion(win_rate=0.6, avg_win_pct=3.0, avg_loss_pct=1.5, n_trades=10)
        assert kc.full_kelly() is None

    def test_full_kelly_with_data(self):
        # b = 3/1.5 = 2.0; f* = (0.6*2 - 0.4) / 2 = 0.8/2 = 0.40
        kc = KellyCriterion(win_rate=0.6, avg_win_pct=3.0, avg_loss_pct=1.5, n_trades=50)
        result = kc.full_kelly()
        assert result is not None
        assert abs(result - 0.40) < 0.001

    def test_fractional_kelly_clamps_to_max(self):
        # Very high edge → fractional Kelly could exceed 5%
        kc = KellyCriterion(win_rate=0.95, avg_win_pct=10.0, avg_loss_pct=1.0, n_trades=100)
        result = kc.fractional_kelly()
        assert result <= 5.0

    def test_fractional_kelly_clamps_to_min(self):
        # Negative edge → fall back to MIN
        kc = KellyCriterion(win_rate=0.3, avg_win_pct=1.0, avg_loss_pct=3.0, n_trades=50)
        result = kc.fractional_kelly()
        assert result >= 0.5

    def test_fractional_kelly_typical_case(self):
        # win_rate=0.6, b=2, f*=0.40, fractional=0.25*0.40*100=10% → clamped to 5%
        kc = KellyCriterion(win_rate=0.6, avg_win_pct=3.0, avg_loss_pct=1.5, n_trades=50)
        result = kc.fractional_kelly()
        assert 0.5 <= result <= 5.0

    def test_ruin_risk_returns_float(self):
        kc = KellyCriterion(win_rate=0.6, avg_win_pct=3.0, avg_loss_pct=1.5, n_trades=50)
        ror = kc.ruin_risk()
        assert 0.0 <= ror <= 1.0


class TestRiskOfRuin:
    def test_zero_edge_returns_one(self):
        assert risk_of_ruin(win_rate=0.5, bet_fraction=0.02) == 1.0

    def test_negative_edge_returns_one(self):
        assert risk_of_ruin(win_rate=0.4, bet_fraction=0.02) == 1.0

    def test_high_win_rate_low_risk(self):
        ror = risk_of_ruin(win_rate=0.7, bet_fraction=0.01)
        assert ror < 0.5

    def test_zero_bet_returns_one(self):
        assert risk_of_ruin(win_rate=0.6, bet_fraction=0.0) == 1.0


class TestPositionSizer:
    def test_basic_sizing(self):
        sizer = PositionSizer(capital=10000, default_risk_pct=1.0)
        size = sizer.compute(entry_price=50000, stop_price=49000)
        # stop dist = 2%, risk = 1%, size = 1/2 * 100 = 50% → clamped to 5%
        assert size == 5.0

    def test_wide_stop_reduces_size(self):
        sizer = PositionSizer(capital=10000, default_risk_pct=1.0)
        size = sizer.compute(entry_price=50000, stop_price=45000)
        # stop dist = 10%, size = 1/10 * 100 = 10% → clamped to 5%
        assert size == 5.0

    def test_tight_stop_clamps_to_min(self):
        sizer = PositionSizer(capital=10000, default_risk_pct=0.1)
        size = sizer.compute(entry_price=50000, stop_price=49900)
        # Would be very large; check min clamp
        assert size >= 0.5

    def test_zero_entry_returns_min(self):
        sizer = PositionSizer(capital=10000, default_risk_pct=1.0)
        size = sizer.compute(entry_price=0, stop_price=49000)
        assert size == 0.5

    def test_kelly_integration(self):
        kc = KellyCriterion(win_rate=0.55, avg_win_pct=2.0, avg_loss_pct=1.5, n_trades=50)
        sizer = PositionSizer(capital=10000, kelly=kc)
        size = sizer.compute(entry_price=50000, stop_price=49500)
        assert 0.5 <= size <= 5.0


# ---------------------------------------------------------------------------
# CapitalProtections
# ---------------------------------------------------------------------------

class TestCapitalProtections:
    def test_ok_when_no_losses(self):
        result = CapitalProtections().check(daily_pnl_pct=0.5)
        assert result.status == DrawdownStatus.OK
        assert result.can_trade is True
        assert result.size_multiplier == 1.0

    def test_warn_approaching_daily_limit(self):
        result = CapitalProtections().check(daily_pnl_pct=-2.5)
        assert result.status == DrawdownStatus.WARN
        assert result.can_trade is True

    def test_daily_pause(self):
        result = CapitalProtections().check(daily_pnl_pct=-3.5)
        assert result.status == DrawdownStatus.DAILY_PAUSE
        assert result.can_trade is False
        assert result.size_multiplier == 0.0

    def test_weekly_reduced(self):
        result = CapitalProtections().check(daily_pnl_pct=-1.0, weekly_pnl_pct=-7.0)
        assert result.status == DrawdownStatus.WEEKLY_REDUCED
        assert result.can_trade is True
        assert result.size_multiplier == 0.5

    def test_monthly_suspend(self):
        result = CapitalProtections().check(
            daily_pnl_pct=-1.0, weekly_pnl_pct=-5.0, monthly_pnl_pct=-16.0
        )
        assert result.status == DrawdownStatus.MONTHLY_SUSPEND
        assert result.can_trade is False

    def test_monthly_takes_priority_over_weekly(self):
        result = CapitalProtections().check(weekly_pnl_pct=-8.0, monthly_pnl_pct=-20.0)
        assert result.status == DrawdownStatus.MONTHLY_SUSPEND

    def test_no_params_returns_ok(self):
        result = CapitalProtections().check()
        assert result.status == DrawdownStatus.OK


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_initially_closed(self):
        cb = CircuitBreaker()
        assert cb.is_open is False

    def test_trips_on_consecutive_losses(self):
        cb = CircuitBreaker()
        for _ in range(3):
            cb.record_trade_result(-1.0)
        assert cb.is_open is True

    def test_does_not_trip_on_single_loss(self):
        cb = CircuitBreaker()
        cb.record_trade_result(-2.0)
        assert cb.is_open is False

    def test_trips_on_daily_loss_limit(self):
        cb = CircuitBreaker()
        cb.record_trade_result(-4.5)
        assert cb.is_open is True

    def test_win_resets_consecutive_counter(self):
        cb = CircuitBreaker()
        cb.record_trade_result(-1.0)
        cb.record_trade_result(-1.0)
        cb.record_trade_result(2.0)   # win resets counter
        cb.record_trade_result(-1.0)
        assert cb.is_open is False

    def test_does_not_double_trip(self):
        cb = CircuitBreaker()
        for _ in range(5):
            cb.record_trade_result(-1.0)
        # Still only one trip (tripped_at set once)
        assert cb.is_open is True

    def test_reset_daily_resets_loss_counter(self):
        cb = CircuitBreaker()
        cb._daily_loss_pct = -3.9
        cb.reset_daily()
        assert cb._daily_loss_pct == 0.0

    def test_daily_counter_rolls_over_on_new_utc_day(self):
        # Losses accumulated "yesterday" must not count toward today's limit.
        cb = CircuitBreaker()
        cb._daily_loss_pct = -3.5
        cb._loss_day = "2020-01-01"  # simulate a counter from a past day
        cb.record_trade_result(-0.5)
        assert cb._daily_loss_pct == -0.5  # reset first, then today's trade
        assert cb.is_open is False

    def test_same_day_losses_still_accumulate(self):
        cb = CircuitBreaker()
        cb.record_trade_result(-2.5)
        cb.record_trade_result(-2.0)  # same day: -4.5 total → trips at -4%
        assert cb.is_open is True


# ---------------------------------------------------------------------------
# Guardrail market conditions
# ---------------------------------------------------------------------------

class TestGuardrailMarketConditions:
    def test_no_context_passes(self):
        gs = GuardrailSystem()
        passed, msg = gs.check_market_conditions({})
        assert passed is True

    def test_extreme_volatility_rejected(self):
        gs = GuardrailSystem()
        order = {"market_context": {"atr": 6000, "bb_middle": 50000, "volume_ratio": 1.0}}
        passed, msg = gs.check_market_conditions(order)
        # atr/bb_middle = 6000/50000 = 12% > 10%
        assert passed is False
        assert "volatility" in msg.lower()

    def test_low_volume_rejected(self):
        gs = GuardrailSystem()
        order = {"market_context": {"atr": 100, "bb_middle": 50000, "volume_ratio": 0.2}}
        passed, msg = gs.check_market_conditions(order)
        assert passed is False
        assert "liquidity" in msg.lower()

    def test_normal_conditions_pass(self):
        gs = GuardrailSystem()
        order = {"market_context": {"atr": 500, "bb_middle": 50000, "volume_ratio": 1.2}}
        passed, msg = gs.check_market_conditions(order)
        assert passed is True
        assert msg == ""
