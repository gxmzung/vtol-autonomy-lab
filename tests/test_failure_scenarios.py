from src.mission_manager import run_simulation
from src.state_machine import FailureCode, MissionState
from src.virtual_fc import SimulationScenario


def test_normal_scenario_completes() -> None:
    result = run_simulation(SimulationScenario.NORMAL)
    assert result.state_machine.state is MissionState.COMPLETE
    assert result.state_machine.failure_code is FailureCode.NONE


def test_takeoff_stall_aborts() -> None:
    result = run_simulation(SimulationScenario.TAKEOFF_STALL)
    assert result.state_machine.state is MissionState.ABORT
    assert result.state_machine.failure_code is FailureCode.TAKEOFF_TIMEOUT


def test_transition_timeout_aborts() -> None:
    result = run_simulation(SimulationScenario.TRANSITION_TIMEOUT)
    assert result.state_machine.state is MissionState.ABORT
    assert result.state_machine.failure_code is FailureCode.FORWARD_TRANSITION_TIMEOUT


def test_link_loss_aborts() -> None:
    result = run_simulation(SimulationScenario.LINK_LOSS)
    assert result.state_machine.state is MissionState.ABORT
    assert result.state_machine.failure_code is FailureCode.CONNECTION_LOST


def test_low_battery_aborts() -> None:
    result = run_simulation(SimulationScenario.LOW_BATTERY)
    assert result.state_machine.state is MissionState.ABORT
    assert result.state_machine.failure_code is FailureCode.LOW_BATTERY


def test_gps_loss_aborts() -> None:
    result = run_simulation(SimulationScenario.GPS_LOSS)
    assert result.state_machine.state is MissionState.ABORT
    assert result.state_machine.failure_code is FailureCode.GPS_LOST


def test_altitude_limit_aborts() -> None:
    result = run_simulation(SimulationScenario.ALTITUDE_LIMIT)
    assert result.state_machine.state is MissionState.ABORT
    assert result.state_machine.failure_code is FailureCode.ALTITUDE_LIMIT_EXCEEDED


def test_airspeed_limit_aborts() -> None:
    result = run_simulation(SimulationScenario.AIRSPEED_LIMIT)
    assert result.state_machine.state is MissionState.ABORT
    assert result.state_machine.failure_code is FailureCode.AIRSPEED_LIMIT_EXCEEDED
