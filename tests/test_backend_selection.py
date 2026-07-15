import pytest

from src.flight_controller import FlightControllerInterface
from src.mavsdk_fc import MavsdkFlightController
from src.mission_manager import create_flight_controller, run_simulation
from src.state_machine import FailureCode, MissionState
from src.virtual_fc import SimulationScenario, VirtualFlightController


def test_create_virtual_backend() -> None:
    controller = create_flight_controller(
        backend="virtual",
        scenario=SimulationScenario.NORMAL,
    )
    assert isinstance(controller, VirtualFlightController)
    assert isinstance(controller, FlightControllerInterface)


def test_create_mavsdk_backend() -> None:
    controller = create_flight_controller(
        backend="mavsdk",
        connection_url="udpin://0.0.0.0:14540",
    )
    assert isinstance(controller, MavsdkFlightController)
    assert isinstance(controller, FlightControllerInterface)


def test_invalid_backend_raises_value_error() -> None:
    with pytest.raises(ValueError):
        create_flight_controller(backend="invalid")  # type: ignore[arg-type]


def test_virtual_backend_still_completes_mission() -> None:
    result = run_simulation(scenario=SimulationScenario.NORMAL)
    assert result.state_machine.state is MissionState.COMPLETE
    assert result.state_machine.failure_code is FailureCode.NONE
