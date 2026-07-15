from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

try:
    from mavsdk import System
except ImportError:  # 테스트 환경에서 mavsdk가 없을 수 있음
    System = None  # type: ignore[assignment]

from src.flight_controller import FlightControllerInterface
from src.mission_context import MissionContext
from src.offboard_controller import OffboardConfig, OffboardController
from src.mission_plan import MissionPlan
from src.mission_raw_uploader import (
    MissionRawProgress,
    MissionRawUploader,
    MissionUploadResult,
)
from src.state_machine import MissionState


class MavsdkFlightController(FlightControllerInterface):
    """MAVSDK를 통해 PX4와 통신하는 실제 비행제어기 어댑터."""

    def __init__(
        self,
        connection_url: str = "udpin://0.0.0.0:14540",
        connection_timeout_s: float = 15.0,
        system: Any | None = None,
        mission_plan: MissionPlan | None = None,
        mission_item_factory: Callable[..., Any] | None = None,
        offboard_setpoint_factory: Callable[..., Any] | None = None,
        offboard_config: OffboardConfig | None = None,
    ) -> None:
        if connection_timeout_s <= 0:
            raise ValueError("연결 제한시간은 0보다 커야 합니다.")

        self.connection_url = connection_url
        self.connection_timeout_s = connection_timeout_s
        self._system = system
        self._mission_plan = mission_plan
        self._mission_item_factory = mission_item_factory
        self._offboard_setpoint_factory = offboard_setpoint_factory
        self._offboard_config = offboard_config

        self._context = MissionContext()
        self._telemetry_tasks: list[asyncio.Task[None]] = []
        self._telemetry_error: str | None = None
        self._mission_uploader: MissionRawUploader | None = None
        self._offboard_controller: OffboardController | None = None
        self._closed = False

    @property
    def context(self) -> MissionContext:
        return self._context

    @property
    def telemetry_error(self) -> str | None:
        return self._telemetry_error

    @property
    def mission_plan(self) -> MissionPlan | None:
        return self._mission_plan

    @property
    def mission_uploader(self) -> MissionRawUploader | None:
        return self._mission_uploader

    @property
    def offboard_controller(self) -> OffboardController | None:
        return self._offboard_controller

    def _require_system(self) -> Any:
        if self._system is None:
            if System is None:
                raise ImportError("mavsdk 패키지가 설치되어 있지 않습니다.")
            self._system = System()
        return self._system

    def _ensure_mission_uploader(self) -> MissionRawUploader:
        if self._mission_uploader is not None:
            return self._mission_uploader

        system = self._require_system()
        mission_raw_plugin = getattr(system, "mission_raw", None)

        if mission_raw_plugin is None:
            raise RuntimeError(
                "연결된 MAVSDK System에 mission_raw 플러그인이 없습니다."
            )

        self._mission_uploader = MissionRawUploader(
            mission_raw_plugin=mission_raw_plugin,
            item_factory=self._mission_item_factory,
        )
        return self._mission_uploader

    def create_offboard_controller(
        self,
        config: OffboardConfig | None = None,
    ) -> OffboardController:
        """MAVSDK offboard 플러그인을 안전 제어 계층으로 감싼다.

        생성만으로 Arm, 이륙 또는 Offboard 시작 명령은 전송하지 않는다.
        """

        if self._offboard_controller is not None:
            return self._offboard_controller

        system = self._require_system()
        offboard_plugin = getattr(system, "offboard", None)
        if offboard_plugin is None:
            raise RuntimeError(
                "연결된 MAVSDK System에 offboard 플러그인이 없습니다."
            )

        self._offboard_controller = OffboardController(
            offboard_plugin=offboard_plugin,
            config=config or self._offboard_config,
            setpoint_factory=self._offboard_setpoint_factory,
        )
        return self._offboard_controller

    async def connect(self) -> None:
        system = self._require_system()
        print(f"[MAVSDK] 연결 시도: {self.connection_url}")
        await system.connect(system_address=self.connection_url)

        async def wait_for_connection() -> None:
            async for state in system.core.connection_state():
                if state.is_connected:
                    self._context.connected = True
                    return

        try:
            await asyncio.wait_for(
                wait_for_connection(),
                timeout=self.connection_timeout_s,
            )
        except TimeoutError as error:
            raise ConnectionError(
                "PX4 연결 제한시간을 초과했습니다: "
                f"{self.connection_timeout_s:.1f}초"
            ) from error

        if getattr(system, "mission_raw", None) is not None:
            self._ensure_mission_uploader()
        print("[MAVSDK] PX4 연결 완료")
        self._start_telemetry_tasks()

    async def upload_mission(
        self,
        mission_plan: MissionPlan | None = None,
        clear_existing: bool = True,
        stop_hold_time_s: float = 1.0,
    ) -> MissionUploadResult:
        """MissionPlan을 PX4 MissionRaw 저장소에 업로드한다.

        이 메서드는 Arm, 이륙 또는 임무 시작 명령을 보내지 않는다.
        """

        selected_plan = mission_plan or self._mission_plan
        if selected_plan is None:
            raise RuntimeError("업로드할 MissionPlan이 설정되지 않았습니다.")

        uploader = self._ensure_mission_uploader()
        result = await uploader.upload(
            mission_plan=selected_plan,
            clear_existing=clear_existing,
            stop_hold_time_s=stop_hold_time_s,
        )

        self._mission_plan = selected_plan
        self._context.mission_uploaded = True
        self._context.mission_started = False
        self._context.mission_paused = False
        self._context.raw_mission_current = 0
        self._context.raw_mission_total = result.uploaded_items
        self._context.raw_mission_progress_pct = 0.0
        self._context.raw_mission_finished = False
        return result

    async def start_uploaded_mission(self) -> None:
        """이미 업로드한 임무를 명시적으로 시작한다."""

        uploader = self._ensure_mission_uploader()
        await uploader.start()
        self._context.mission_started = True
        self._context.mission_paused = False

    async def pause_uploaded_mission(self) -> None:
        """현재 MissionRaw 임무를 일시정지한다."""

        uploader = self._ensure_mission_uploader()
        await uploader.pause()
        self._context.mission_paused = True

    async def clear_uploaded_mission(self) -> None:
        """PX4에 저장된 임무를 삭제하고 로컬 상태를 초기화한다."""

        uploader = self._ensure_mission_uploader()
        await uploader.clear()

        self._context.mission_uploaded = False
        self._context.mission_started = False
        self._context.mission_paused = False
        self._context.raw_mission_current = 0
        self._context.raw_mission_total = 0
        self._context.raw_mission_progress_pct = 0.0
        self._context.raw_mission_finished = False

    async def mission_progress_stream(
        self,
    ) -> AsyncIterator[MissionRawProgress]:
        """MissionRaw 진행률을 수신하면서 MissionContext에 동기화한다."""

        uploader = self._ensure_mission_uploader()

        async for progress in uploader.progress_stream():
            self._apply_mission_progress(progress)
            yield progress

    def _apply_mission_progress(
        self,
        progress: MissionRawProgress,
    ) -> None:
        self._context.raw_mission_current = progress.current
        self._context.raw_mission_total = progress.total
        self._context.raw_mission_progress_pct = progress.progress_pct
        self._context.raw_mission_finished = progress.finished

        if progress.finished:
            self._context.mission_started = False
            self._context.mission_paused = False

    async def arm(self) -> None:
        await self._require_system().action.arm()

    async def takeoff(self, altitude_m: float) -> None:
        if altitude_m <= 0:
            raise ValueError("이륙 고도는 0보다 커야 합니다.")
        system = self._require_system()
        await system.action.set_takeoff_altitude(altitude_m)
        await system.action.takeoff()

    async def transition_to_fixed_wing(self) -> None:
        await self._require_system().action.transition_to_fixedwing()

    async def transition_to_multicopter(self) -> None:
        await self._require_system().action.transition_to_multicopter()

    async def return_to_launch(self) -> None:
        await self._require_system().action.return_to_launch()

    async def land(self) -> None:
        await self._require_system().action.land()

    async def update(
        self,
        state: MissionState,
        dt_s: float,
        state_elapsed_s: float,
    ) -> MissionContext:
        del state_elapsed_s

        if dt_s <= 0:
            raise ValueError("갱신 간격은 0보다 커야 합니다.")

        if self._telemetry_error is not None:
            self._context.failsafe_triggered = True
            self._context.failsafe_code = "EXTERNAL_FAILSAFE"
            self._context.failsafe_reason = self._telemetry_error
            self._context.failsafe_action = "ABORT"

        if state is MissionState.HOVER:
            self._context.hover_stable = (
                self._context.in_air
                and self._context.vtol_state == "MC"
                and abs(self._context.airspeed_m_s) <= 2.0
            )

        if state is MissionState.FORWARD_TRANSITION:
            self._context.forward_transition_complete = (
                self._context.vtol_state == "FW"
            )

        if state is MissionState.BACK_TRANSITION:
            self._context.back_transition_complete = (
                self._context.vtol_state == "MC"
            )

        if state is MissionState.RETURN_HOME:
            self._context.returned_home = (
                self._context.flight_mode == "LAND"
                or not self._context.in_air
            )

        if state is MissionState.LAND:
            self._context.landed = not self._context.in_air

        return self._context

    def _start_telemetry_tasks(self) -> None:
        if self._telemetry_tasks:
            return

        system = self._require_system()

        watchers: list[
            tuple[
                Callable[[], AsyncIterator[Any]],
                Callable[[Any], None],
            ]
        ] = [
            (system.core.connection_state, self._apply_connection_state),
            (system.telemetry.health, self._apply_health),
            (system.telemetry.armed, self._apply_armed),
            (system.telemetry.position, self._apply_position),
            (
                system.telemetry.fixedwing_metrics,
                self._apply_fixedwing_metrics,
            ),
            (system.telemetry.vtol_state, self._apply_vtol_state),
            (system.telemetry.in_air, self._apply_in_air),
            (system.telemetry.battery, self._apply_battery),
            (system.telemetry.gps_info, self._apply_gps_info),
            (system.telemetry.flight_mode, self._apply_flight_mode),
        ]

        for stream_factory, callback in watchers:
            task = asyncio.create_task(
                self._watch_stream(
                    stream_factory=stream_factory,
                    callback=callback,
                )
            )
            self._telemetry_tasks.append(task)

    async def _watch_stream(
        self,
        stream_factory: Callable[[], AsyncIterator[Any]],
        callback: Callable[[Any], None],
    ) -> None:
        try:
            async for value in stream_factory():
                callback(value)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._telemetry_error = f"{type(error).__name__}: {error}"

    def _apply_connection_state(self, state: Any) -> None:
        self._context.connected = bool(state.is_connected)

    def _apply_health(self, health: Any) -> None:
        is_armable = bool(getattr(health, "is_armable", False))
        self._context.health_ok = bool(
            is_armable
            and health.is_global_position_ok
            and health.is_home_position_ok
        )

    def _apply_armed(self, armed: Any) -> None:
        self._context.armed = bool(armed)

    def _apply_position(self, position: Any) -> None:
        self._context.latitude_deg = float(position.latitude_deg)
        self._context.longitude_deg = float(position.longitude_deg)
        self._context.altitude_m = float(position.relative_altitude_m)

    def _apply_fixedwing_metrics(self, metrics: Any) -> None:
        self._context.airspeed_m_s = float(metrics.airspeed_m_s)

    def _apply_vtol_state(self, vtol_state: Any) -> None:
        self._context.vtol_state = self._enum_name(vtol_state)

    def _apply_in_air(self, in_air: Any) -> None:
        self._context.in_air = bool(in_air)

    def _apply_battery(self, battery: Any) -> None:
        raw = float(battery.remaining_percent)
        self._context.battery_remaining_pct = (
            raw * 100.0 if 0.0 <= raw <= 1.0 else raw
        )

    def _apply_gps_info(self, gps_info: Any) -> None:
        self._context.satellites = int(gps_info.num_satellites)
        self._context.gps_fix = self._enum_name(gps_info.fix_type)

    def _apply_flight_mode(self, flight_mode: Any) -> None:
        self._context.flight_mode = self._enum_name(flight_mode)

    @staticmethod
    def _enum_name(value: Any) -> str:
        name = getattr(value, "name", None)
        if name is not None:
            return str(name)
        return str(value)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        for task in self._telemetry_tasks:
            task.cancel()
        if self._telemetry_tasks:
            await asyncio.gather(
                *self._telemetry_tasks,
                return_exceptions=True,
            )
        self._telemetry_tasks.clear()
