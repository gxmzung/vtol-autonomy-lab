from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from src.mission_plan import MissionPlan
from src.mission_raw_builder import build_mavsdk_mission_items


@dataclass(frozen=True, slots=True)
class MissionUploadResult:
    mission_name: str
    uploaded_items: int
    cleared_previous_mission: bool


@dataclass(frozen=True, slots=True)
class MissionRawProgress:
    current: int
    total: int
    progress_pct: float
    finished: bool

    @classmethod
    def from_sdk(cls, progress: Any) -> MissionRawProgress:
        current = int(progress.current)
        total = int(progress.total)

        if current < 0 or total < 0:
            raise ValueError("임무 진행값은 음수일 수 없습니다.")
        if current > total:
            raise ValueError("현재 임무 순번은 전체 항목 수를 초과할 수 없습니다.")

        if total == 0:
            progress_pct = 0.0
            finished = False
        else:
            progress_pct = min(100.0, current / total * 100.0)
            finished = current == total

        return cls(
            current=current,
            total=total,
            progress_pct=progress_pct,
            finished=finished,
        )


class MissionRawUploader:
    """MAVSDK mission_raw 플러그인의 업로드·실행·진행률 계층."""

    def __init__(
        self,
        mission_raw_plugin: Any,
        item_factory: Callable[..., Any] | None = None,
    ) -> None:
        if mission_raw_plugin is None:
            raise ValueError("mission_raw 플러그인이 필요합니다.")

        required_methods = (
            "upload_mission",
            "start_mission",
            "pause_mission",
            "clear_mission",
            "mission_progress",
        )
        missing = [
            method
            for method in required_methods
            if not callable(getattr(mission_raw_plugin, method, None))
        ]
        if missing:
            raise TypeError(
                "mission_raw 플러그인에 필요한 메서드가 없습니다: "
                + ", ".join(missing)
            )

        self._plugin = mission_raw_plugin
        self._item_factory = item_factory
        self._last_uploaded_plan: MissionPlan | None = None
        self._latest_progress = MissionRawProgress(
            current=0,
            total=0,
            progress_pct=0.0,
            finished=False,
        )

    @property
    def latest_progress(self) -> MissionRawProgress:
        return self._latest_progress

    @property
    def last_uploaded_plan(self) -> MissionPlan | None:
        return self._last_uploaded_plan

    async def upload(
        self,
        mission_plan: MissionPlan,
        clear_existing: bool = True,
        stop_hold_time_s: float = 1.0,
    ) -> MissionUploadResult:
        mission_items = build_mavsdk_mission_items(
            mission_plan=mission_plan,
            item_factory=self._item_factory,
            stop_hold_time_s=stop_hold_time_s,
        )

        if clear_existing:
            await self._plugin.clear_mission()

        await self._plugin.upload_mission(mission_items)
        self._last_uploaded_plan = mission_plan
        self._latest_progress = MissionRawProgress(
            current=0,
            total=len(mission_items),
            progress_pct=0.0,
            finished=False,
        )

        return MissionUploadResult(
            mission_name=mission_plan.name,
            uploaded_items=len(mission_items),
            cleared_previous_mission=clear_existing,
        )

    async def download(self) -> list[Any]:
        """FC에 저장된 MissionRaw 항목을 읽기 전용으로 내려받는다."""

        download_method = getattr(self._plugin, "download_mission", None)
        if not callable(download_method):
            raise RuntimeError(
                "mission_raw 플러그인이 download_mission()을 지원하지 않습니다."
            )

        mission_items = await download_method()
        return list(mission_items)

    async def start(self) -> None:
        if self._last_uploaded_plan is None:
            raise RuntimeError("임무를 업로드한 뒤 시작해야 합니다.")
        await self._plugin.start_mission()

    async def pause(self) -> None:
        await self._plugin.pause_mission()

    async def clear(self) -> None:
        await self._plugin.clear_mission()
        self._last_uploaded_plan = None
        self._latest_progress = MissionRawProgress(
            current=0,
            total=0,
            progress_pct=0.0,
            finished=False,
        )

    async def progress_stream(self) -> AsyncIterator[MissionRawProgress]:
        async for sdk_progress in self._plugin.mission_progress():
            progress = MissionRawProgress.from_sdk(sdk_progress)
            self._latest_progress = progress
            yield progress
