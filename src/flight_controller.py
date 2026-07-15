from __future__ import annotations

from abc import ABC, abstractmethod

from src.mission_context import MissionContext
from src.state_machine import MissionState


class FlightControllerInterface(ABC):
    @property
    @abstractmethod
    def context(self) -> MissionContext:
        pass

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def arm(self) -> None:
        pass

    @abstractmethod
    async def takeoff(self, altitude_m: float) -> None:
        pass

    @abstractmethod
    async def transition_to_fixed_wing(self) -> None:
        pass

    @abstractmethod
    async def transition_to_multicopter(self) -> None:
        pass

    @abstractmethod
    async def return_to_launch(self) -> None:
        pass

    @abstractmethod
    async def land(self) -> None:
        pass

    @abstractmethod
    async def update(
        self,
        state: MissionState,
        dt_s: float,
        state_elapsed_s: float,
    ) -> MissionContext:
        pass

    async def close(self) -> None:
        pass
