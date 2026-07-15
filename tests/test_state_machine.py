import pytest

from src.mission_context import MissionContext
from src.state_machine import FailureCode, MissionState, MissionStateMachine


def test_initial_state() -> None:
    machine = MissionStateMachine()
    assert machine.state is MissionState.IDLE


def test_invalid_takeoff_altitude() -> None:
    with pytest.raises(ValueError):
        MissionStateMachine(takeoff_altitude_m=0.0)


def test_connection_moves_to_preflight() -> None:
    machine = MissionStateMachine()
    context = MissionContext(connected=True)
    result = machine.update(context, now_s=0.5)
    assert result is MissionState.PREFLIGHT


def test_external_failsafe_aborts() -> None:
    machine = MissionStateMachine()
    context = MissionContext(connected=True, failsafe_triggered=True)
    result = machine.update(context, now_s=1.0)
    assert result is MissionState.ABORT
    assert machine.failure_code is FailureCode.EXTERNAL_FAILSAFE
