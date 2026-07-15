from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

try:
    from mavsdk.offboard import VelocityNedYaw
except ImportError:  # 테스트 환경에서는 factory를 주입한다.
    VelocityNedYaw = None  # type: ignore[assignment]

from src.target_estimate import TargetEstimate


class OffboardState(str, Enum):
    IDLE = "IDLE"
    PRIMED = "PRIMED"
    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"


@dataclass(frozen=True, slots=True)
class OffboardConfig:
    horizontal_gain: float = 0.35
    vertical_gain: float = 0.30
    maximum_horizontal_speed_m_s: float = 4.0
    maximum_vertical_speed_m_s: float = 1.5
    horizontal_tolerance_m: float = 1.5
    vertical_tolerance_m: float = 1.0

    def __post_init__(self) -> None:
        positive_values = (
            self.horizontal_gain,
            self.vertical_gain,
            self.maximum_horizontal_speed_m_s,
            self.maximum_vertical_speed_m_s,
            self.horizontal_tolerance_m,
            self.vertical_tolerance_m,
        )
        if any(value <= 0.0 for value in positive_values):
            raise ValueError("Offboard 설정값은 모두 0보다 커야 합니다.")


@dataclass(frozen=True, slots=True)
class VelocityNedCommand:
    north_m_s: float
    east_m_s: float
    down_m_s: float
    yaw_deg: float

    @property
    def horizontal_speed_m_s(self) -> float:
        return math.hypot(self.north_m_s, self.east_m_s)


class OffboardController:
    """표적 상대 위치를 MAVSDK NED 속도 Setpoint로 변환한다."""

    def __init__(
        self,
        offboard_plugin: Any,
        config: OffboardConfig | None = None,
        setpoint_factory: Callable[..., Any] | None = None,
    ) -> None:
        if offboard_plugin is None:
            raise ValueError("offboard 플러그인이 필요합니다.")

        required_methods = (
            "set_velocity_ned",
            "start",
            "stop",
        )
        missing = [
            method
            for method in required_methods
            if not callable(getattr(offboard_plugin, method, None))
        ]
        if missing:
            raise TypeError(
                "offboard 플러그인에 필요한 메서드가 없습니다: "
                + ", ".join(missing)
            )

        self._plugin = offboard_plugin
        self.config = config or OffboardConfig()
        self._setpoint_factory = setpoint_factory
        self.state = OffboardState.IDLE
        self.last_command: VelocityNedCommand | None = None

    def _build_sdk_setpoint(
        self,
        command: VelocityNedCommand,
    ) -> Any:
        if self._setpoint_factory is not None:
            return self._setpoint_factory(
                command.north_m_s,
                command.east_m_s,
                command.down_m_s,
                command.yaw_deg,
            )

        if VelocityNedYaw is None:
            raise ImportError(
                "mavsdk.offboard.VelocityNedYaw를 사용할 수 없습니다."
            )

        return VelocityNedYaw(
            command.north_m_s,
            command.east_m_s,
            command.down_m_s,
            command.yaw_deg,
        )

    @staticmethod
    def hold_command(yaw_deg: float = 0.0) -> VelocityNedCommand:
        return VelocityNedCommand(
            north_m_s=0.0,
            east_m_s=0.0,
            down_m_s=0.0,
            yaw_deg=yaw_deg,
        )

    def compute_approach_command(
        self,
        target: TargetEstimate,
    ) -> VelocityNedCommand:
        north_m_s = (
            target.relative_north_m
            * self.config.horizontal_gain
        )
        east_m_s = (
            target.relative_east_m
            * self.config.horizontal_gain
        )

        horizontal_speed_m_s = math.hypot(
            north_m_s,
            east_m_s,
        )
        if (
            horizontal_speed_m_s
            > self.config.maximum_horizontal_speed_m_s
        ):
            ratio = (
                self.config.maximum_horizontal_speed_m_s
                / horizontal_speed_m_s
            )
            north_m_s *= ratio
            east_m_s *= ratio

        down_m_s = max(
            -self.config.maximum_vertical_speed_m_s,
            min(
                self.config.maximum_vertical_speed_m_s,
                target.relative_down_m
                * self.config.vertical_gain,
            ),
        )

        return VelocityNedCommand(
            north_m_s=north_m_s,
            east_m_s=east_m_s,
            down_m_s=down_m_s,
            yaw_deg=target.bearing_deg,
        )

    def is_target_aligned(
        self,
        target: TargetEstimate,
    ) -> bool:
        return target.is_aligned(
            horizontal_tolerance_m=(
                self.config.horizontal_tolerance_m
            ),
            vertical_tolerance_m=(
                self.config.vertical_tolerance_m
            ),
        )

    async def _send(
        self,
        command: VelocityNedCommand,
    ) -> VelocityNedCommand:
        setpoint = self._build_sdk_setpoint(command)
        await self._plugin.set_velocity_ned(setpoint)
        self.last_command = command
        return command

    async def prime(self, yaw_deg: float = 0.0) -> None:
        if self.state is OffboardState.ACTIVE:
            raise RuntimeError("활성 Offboard를 다시 준비할 수 없습니다.")

        await self._send(self.hold_command(yaw_deg))
        self.state = OffboardState.PRIMED

    async def start(self) -> None:
        if self.state is not OffboardState.PRIMED:
            raise RuntimeError(
                "초기 Setpoint를 전송한 뒤 Offboard를 시작해야 합니다."
            )

        await self._plugin.start()
        self.state = OffboardState.ACTIVE

    async def send_target_command(
        self,
        target: TargetEstimate,
    ) -> VelocityNedCommand:
        if self.state is not OffboardState.ACTIVE:
            raise RuntimeError("Offboard가 활성화되지 않았습니다.")

        command = self.compute_approach_command(target)
        return await self._send(command)

    async def hold(self) -> VelocityNedCommand:
        if self.state not in {
            OffboardState.PRIMED,
            OffboardState.ACTIVE,
        }:
            raise RuntimeError("Offboard 준비 또는 활성 상태가 아닙니다.")

        yaw_deg = (
            self.last_command.yaw_deg
            if self.last_command is not None
            else 0.0
        )
        return await self._send(self.hold_command(yaw_deg))

    async def stop(self) -> None:
        if self.state is OffboardState.ACTIVE:
            await self._plugin.stop()

        self.state = OffboardState.STOPPED
