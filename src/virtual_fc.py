from __future__ import annotations

from enum import Enum

from src.flight_controller import FlightControllerInterface
from src.mission_context import MissionContext
from src.mission_plan import (
    MissionPlan,
    NavigationUpdate,
    Waypoint,
    WaypointNavigator,
    haversine_distance_m,
)
from src.state_machine import MissionState


class SimulationScenario(str, Enum):
    NORMAL = "normal"
    TAKEOFF_STALL = "takeoff_stall"
    TRANSITION_TIMEOUT = "transition_timeout"
    LINK_LOSS = "link_loss"
    LOW_BATTERY = "low_battery"
    GPS_LOSS = "gps_loss"
    ALTITUDE_LIMIT = "altitude_limit"
    AIRSPEED_LIMIT = "airspeed_limit"


class VirtualFlightController(FlightControllerInterface):
    def __init__(
        self,
        scenario: SimulationScenario,
        takeoff_altitude_m: float = 10.0,
        mission_plan: MissionPlan | None = None,
        target_waypoint_name: str = "REP",
    ) -> None:
        if takeoff_altitude_m <= 0:
            raise ValueError("이륙 고도는 0보다 커야 합니다.")

        self.scenario = scenario
        self.takeoff_altitude_m = takeoff_altitude_m
        self.mission_plan = mission_plan
        self.target_waypoint_name = target_waypoint_name

        self.time_s = 0.0
        self._context = MissionContext()

        self._takeoff_requested = False
        self._fixed_wing_requested = False
        self._multicopter_requested = False
        self._rtl_requested = False
        self._land_requested = False

        self.navigator: WaypointNavigator | None = None

        if self.mission_plan is not None:
            self.navigator = WaypointNavigator(mission_plan=self.mission_plan)
            first_waypoint = self.mission_plan.waypoints[0]
            self._context.latitude_deg = first_waypoint.latitude_deg
            self._context.longitude_deg = first_waypoint.longitude_deg
            self._context.current_waypoint_name = first_waypoint.name

    @property
    def context(self) -> MissionContext:
        return self._context

    async def connect(self) -> None:
        self._context.connected = True
        self._context.gps_fix = "FIX_3D"
        self._context.satellites = 15
        self._context.flight_mode = "STANDBY"
        self._context.vtol_state = "MC"

    async def arm(self) -> None:
        if not self._context.connected:
            raise ConnectionError("FC가 연결되지 않아 Arm할 수 없습니다.")
        if not self._context.health_ok:
            raise RuntimeError("비행 전 상태 점검이 완료되지 않았습니다.")
        self._context.armed = True
        self._context.flight_mode = "HOLD"

    async def takeoff(self, altitude_m: float) -> None:
        if altitude_m <= 0:
            raise ValueError("이륙 고도는 0보다 커야 합니다.")
        if not self._context.armed:
            raise RuntimeError("Arm되지 않은 기체는 이륙할 수 없습니다.")
        self.takeoff_altitude_m = altitude_m
        self._takeoff_requested = True
        self._context.flight_mode = "TAKEOFF"
        self._context.vtol_state = "MC"

    async def transition_to_fixed_wing(self) -> None:
        if not self._context.armed:
            raise RuntimeError("Arm되지 않은 기체는 천이할 수 없습니다.")
        self._fixed_wing_requested = True
        self._multicopter_requested = False
        self._context.vtol_state = "TRANSITION_TO_FW"

    async def transition_to_multicopter(self) -> None:
        if not self._context.armed:
            raise RuntimeError("Arm되지 않은 기체는 역천이할 수 없습니다.")
        self._multicopter_requested = True
        self._fixed_wing_requested = False
        self._context.vtol_state = "TRANSITION_TO_MC"

    async def return_to_launch(self) -> None:
        if not self._context.armed:
            raise RuntimeError("Arm되지 않은 기체는 복귀할 수 없습니다.")
        self._rtl_requested = True
        self._context.flight_mode = "RTL"

    async def land(self) -> None:
        if not self._context.armed:
            raise RuntimeError("Arm되지 않은 기체는 착륙할 수 없습니다.")
        self._land_requested = True
        self._context.flight_mode = "LAND"

    def _move_toward_waypoint(
        self,
        waypoint: Waypoint,
        speed_m_s: float,
        dt_s: float,
    ) -> None:
        distance_m = haversine_distance_m(
            latitude_a_deg=self._context.latitude_deg,
            longitude_a_deg=self._context.longitude_deg,
            latitude_b_deg=waypoint.latitude_deg,
            longitude_b_deg=waypoint.longitude_deg,
        )

        if distance_m <= 0.01:
            self._context.latitude_deg = waypoint.latitude_deg
            self._context.longitude_deg = waypoint.longitude_deg
        else:
            movement_m = min(speed_m_s * dt_s, distance_m)
            movement_ratio = movement_m / distance_m
            self._context.latitude_deg += (
                waypoint.latitude_deg - self._context.latitude_deg
            ) * movement_ratio
            self._context.longitude_deg += (
                waypoint.longitude_deg - self._context.longitude_deg
            ) * movement_ratio

        altitude_difference_m = waypoint.relative_altitude_m - self._context.altitude_m
        maximum_altitude_change_m = 3.0 * dt_s
        altitude_change_m = max(
            -maximum_altitude_change_m,
            min(maximum_altitude_change_m, altitude_difference_m),
        )
        self._context.altitude_m += altitude_change_m

    def _sync_navigation_context(self, update: NavigationUpdate) -> None:
        if self.navigator is None:
            return

        self._context.waypoint_index = self.navigator.current_index
        self._context.waypoint_progress_pct = update.progress_pct
        self._context.navigation_complete = update.mission_completed
        current_target = self.navigator.current_waypoint
        self._context.current_waypoint_name = current_target.name

        if update.mission_completed:
            self._context.distance_to_waypoint_m = 0.0
            return

        self._context.distance_to_waypoint_m = haversine_distance_m(
            latitude_a_deg=self._context.latitude_deg,
            longitude_a_deg=self._context.longitude_deg,
            latitude_b_deg=current_target.latitude_deg,
            longitude_b_deg=current_target.longitude_deg,
        )

    def _advance_navigation(
        self,
        speed_m_s: float,
        dt_s: float,
    ) -> NavigationUpdate | None:
        if self.navigator is None:
            return None

        target_waypoint = self.navigator.current_waypoint
        self._move_toward_waypoint(target_waypoint, speed_m_s, dt_s)
        update = self.navigator.update_position(
            latitude_deg=self._context.latitude_deg,
            longitude_deg=self._context.longitude_deg,
        )
        self._sync_navigation_context(update)
        return update

    def _inject_faults(self, state: MissionState) -> None:
        if self.scenario is SimulationScenario.LOW_BATTERY and self.time_s >= 9.0:
            self._context.battery_remaining_pct = 15.0

        if self.scenario is SimulationScenario.GPS_LOSS and self.time_s >= 9.0:
            self._context.gps_fix = "NO_FIX"
            self._context.satellites = 0

        if self.scenario is SimulationScenario.ALTITUDE_LIMIT and self.time_s >= 6.5:
            self._context.altitude_m = 130.0

        if self.scenario is SimulationScenario.AIRSPEED_LIMIT and state is MissionState.CRUISE:
            self._context.airspeed_m_s = 45.0

    async def update(
        self,
        state: MissionState,
        dt_s: float,
        state_elapsed_s: float,
    ) -> MissionContext:
        if dt_s <= 0:
            raise ValueError("시뮬레이션 간격은 0보다 커야 합니다.")

        self.time_s += dt_s

        if self.scenario is SimulationScenario.LINK_LOSS and self.time_s >= 6.0:
            self._context.connected = False
            return self._context

        if state is MissionState.PREFLIGHT:
            self._context.flight_mode = "PREFLIGHT"
            if state_elapsed_s >= 1.0:
                self._context.health_ok = True

        elif state is MissionState.TAKEOFF:
            if (
                self._takeoff_requested
                and self.scenario is not SimulationScenario.TAKEOFF_STALL
            ):
                self._context.altitude_m += 3.0 * dt_s
                self._context.altitude_m = min(
                    self._context.altitude_m,
                    self.takeoff_altitude_m + 0.5,
                )
                self._context.in_air = self._context.altitude_m > 0.5

        elif state is MissionState.HOVER:
            self._context.flight_mode = "HOLD"
            self._context.vtol_state = "MC"
            self._context.airspeed_m_s = 0.0
            if state_elapsed_s >= 1.0:
                self._context.hover_stable = True

        elif state is MissionState.FORWARD_TRANSITION:
            if self._fixed_wing_requested:
                self._context.flight_mode = "MISSION"
                self._context.airspeed_m_s = min(
                    18.0,
                    self._context.airspeed_m_s + 4.0 * dt_s,
                )
                if (
                    self.scenario is not SimulationScenario.TRANSITION_TIMEOUT
                    and state_elapsed_s >= 2.0
                ):
                    self._context.forward_transition_complete = True
                    self._context.vtol_state = "FW"

        elif state is MissionState.CRUISE:
            self._context.flight_mode = "MISSION"
            self._context.vtol_state = "FW"
            self._context.airspeed_m_s = 18.0
            navigation_update = self._advance_navigation(speed_m_s=18.0, dt_s=dt_s)

            if navigation_update is None:
                if state_elapsed_s >= 2.0:
                    self._context.target_detected = True
            elif (
                navigation_update.waypoint_reached
                and navigation_update.current_waypoint_name == self.target_waypoint_name
            ):
                self._context.target_detected = True

        elif state is MissionState.TARGET_SEARCH:
            self._context.flight_mode = "HOLD"
            self._context.airspeed_m_s = 12.0
            if state_elapsed_s >= 1.5:
                self._context.search_complete = True

        elif state is MissionState.BACK_TRANSITION:
            if self._multicopter_requested:
                self._context.airspeed_m_s = max(
                    0.0,
                    self._context.airspeed_m_s - 4.0 * dt_s,
                )
                if state_elapsed_s >= 2.0:
                    self._context.back_transition_complete = True
                    self._context.vtol_state = "MC"

        elif state is MissionState.RETURN_HOME:
            self._context.flight_mode = "RTL"
            self._context.vtol_state = "MC"
            self._context.airspeed_m_s = 12.0

            if self.navigator is None:
                if self._rtl_requested and state_elapsed_s >= 2.0:
                    self._context.returned_home = True
            elif self._rtl_requested:
                navigation_update = self._advance_navigation(speed_m_s=12.0, dt_s=dt_s)
                if navigation_update is not None and navigation_update.mission_completed:
                    self._context.returned_home = True

        elif state is MissionState.LAND:
            self._context.flight_mode = "LAND"
            self._context.vtol_state = "MC"
            self._context.airspeed_m_s = 0.0
            if self._land_requested:
                self._context.altitude_m = max(
                    0.0,
                    self._context.altitude_m - 2.5 * dt_s,
                )
                if self._context.altitude_m <= 0.1:
                    self._context.altitude_m = 0.0
                    self._context.landed = True
                    self._context.in_air = False
                    self._context.armed = False

        self._inject_faults(state)
        return self._context
