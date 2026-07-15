import sys

from src.hybrid_mission_simulator import HybridSimulationScenario
from src.mission_manager import parse_arguments


def test_parse_arguments_supports_hybrid_demo(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mission_manager",
            "--hybrid-demo",
            "--hybrid-scenario",
            "tracking_loss",
        ],
    )

    args = parse_arguments()

    assert args.hybrid_demo is True
    assert (
        args.hybrid_scenario
        == HybridSimulationScenario.TRACKING_LOSS.value
    )
