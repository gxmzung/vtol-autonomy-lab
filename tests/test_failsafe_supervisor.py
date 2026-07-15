import pytest

from src.failsafe_supervisor import (
    FailsafeAction,
    FailsafeConfig,
    FailsafeLevel,
    FailsafeSupervisor,
)
from src.mission_context import MissionContext
from src.state_machine import FailureCode, MissionState


def healthy_context() -> MissionContext:
    return MissionContext(
        connected=True,
        health_ok=True,
        armed=True,
        in_air=True,
        altitude_m=20.0,
        airspeed_m_s=18.0,
        battery_remaining_pct=80.0,
        gps_fix="FIX_3D",
        satellites=14,
    )


def test_normal_context_continues() -> None:
    decision = FailsafeSupervisor().evaluate(
        healthy_context(),
        MissionState.CRUISE,
    )
    assert decision.level is FailsafeLevel.NORMAL
    assert decision.action is FailsafeAction.CONTINUE
    assert decision.failure_code is FailureCode.NONE
    assert decision.triggered is False


def test_low_battery_warning_does_not_abort() -> None:
    context = healthy_context()
    context.battery_remaining_pct = 25.0
    decision = FailsafeSupervisor().evaluate(context, MissionState.CRUISE)
    assert decision.level is FailsafeLevel.WARNING
    assert decision.action is FailsafeAction.WARN
    assert decision.triggered is False


def test_critical_battery_triggers_rtl() -> None:
    context = healthy_context()
    context.battery_remaining_pct = 15.0
    decision = FailsafeSupervisor().evaluate(context, MissionState.CRUISE)
    assert decision.triggered is True
    assert decision.action is FailsafeAction.RTL
    assert decision.failure_code is FailureCode.LOW_BATTERY


def test_gps_loss_in_air_triggers_rtl() -> None:
    context = healthy_context()
    context.gps_fix = "NO_FIX"
    context.satellites = 0
    decision = FailsafeSupervisor().evaluate(context, MissionState.CRUISE)
    assert decision.triggered is True
    assert decision.failure_code is FailureCode.GPS_LOST


def test_gps_loss_on_ground_does_not_trigger() -> None:
    context = healthy_context()
    context.in_air = False
    context.gps_fix = "NO_FIX"
    context.satellites = 0
    decision = FailsafeSupervisor().evaluate(context, MissionState.PREFLIGHT)
    assert decision.triggered is False


def test_altitude_limit_triggers_land() -> None:
    context = healthy_context()
    context.altitude_m = 130.0
    decision = FailsafeSupervisor().evaluate(context, MissionState.CRUISE)
    assert decision.triggered is True
    assert decision.action is FailsafeAction.LAND
    assert decision.failure_code is FailureCode.ALTITUDE_LIMIT_EXCEEDED


def test_airspeed_limit_triggers_rtl() -> None:
    context = healthy_context()
    context.airspeed_m_s = 40.0
    decision = FailsafeSupervisor().evaluate(context, MissionState.CRUISE)
    assert decision.triggered is True
    assert decision.action is FailsafeAction.RTL
    assert decision.failure_code is FailureCode.AIRSPEED_LIMIT_EXCEEDED


def test_apply_writes_decision_into_context() -> None:
    context = healthy_context()
    context.battery_remaining_pct = 10.0
    supervisor = FailsafeSupervisor()
    decision = supervisor.apply(context, MissionState.CRUISE)
    assert context.failsafe_triggered is True
    assert context.failsafe_code == FailureCode.LOW_BATTERY.name
    assert context.failsafe_action == FailsafeAction.RTL.value
    assert context.failsafe_reason == decision.reason


def test_invalid_config_rejects_threshold_order() -> None:
    with pytest.raises(ValueError):
        FailsafeConfig(
            battery_warning_pct=20.0,
            battery_critical_pct=25.0,
        )
