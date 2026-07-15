import asyncio
from types import SimpleNamespace

import pytest

from src.mission_plan import MissionPlan, Waypoint
from src.mission_raw_uploader import MissionRawProgress, MissionRawUploader


def create_plan() -> MissionPlan:
    return MissionPlan(
        name="upload_test",
        waypoints=(
            Waypoint("HOME", 36.321, 127.408, 10.0, fly_through=False),
            Waypoint("WPT1", 36.322, 127.409, 20.0),
        ),
    )


class FakeMissionRawPlugin:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def upload_mission(self, items) -> None:
        self.calls.append(("upload_mission", items))

    async def start_mission(self) -> None:
        self.calls.append(("start_mission", None))

    async def pause_mission(self) -> None:
        self.calls.append(("pause_mission", None))

    async def clear_mission(self) -> None:
        self.calls.append(("clear_mission", None))

    async def mission_progress(self):
        for current, total in ((0, 2), (1, 2), (2, 2)):
            yield SimpleNamespace(current=current, total=total)


def fake_item_factory(*args):
    return SimpleNamespace(seq=args[0], x=args[9], y=args[10])


def test_upload_clears_then_uploads() -> None:
    async def run_test() -> None:
        plugin = FakeMissionRawPlugin()
        uploader = MissionRawUploader(plugin, item_factory=fake_item_factory)

        result = await uploader.upload(create_plan())

        assert result.uploaded_items == 2
        assert result.cleared_previous_mission is True
        assert [call[0] for call in plugin.calls] == ["clear_mission", "upload_mission"]
        uploaded = plugin.calls[1][1]
        assert [item.seq for item in uploaded] == [0, 1]

    asyncio.run(run_test())


def test_start_requires_uploaded_mission() -> None:
    async def run_test() -> None:
        uploader = MissionRawUploader(
            FakeMissionRawPlugin(),
            item_factory=fake_item_factory,
        )

        with pytest.raises(RuntimeError):
            await uploader.start()

    asyncio.run(run_test())


def test_start_pause_and_clear_commands() -> None:
    async def run_test() -> None:
        plugin = FakeMissionRawPlugin()
        uploader = MissionRawUploader(plugin, item_factory=fake_item_factory)

        await uploader.upload(create_plan(), clear_existing=False)
        await uploader.start()
        await uploader.pause()
        await uploader.clear()

        assert [call[0] for call in plugin.calls] == [
            "upload_mission",
            "start_mission",
            "pause_mission",
            "clear_mission",
        ]
        assert uploader.last_uploaded_plan is None
        assert uploader.latest_progress.total == 0

    asyncio.run(run_test())


def test_progress_stream_updates_latest_progress() -> None:
    async def run_test() -> None:
        plugin = FakeMissionRawPlugin()
        uploader = MissionRawUploader(plugin, item_factory=fake_item_factory)
        values = [progress async for progress in uploader.progress_stream()]

        assert [value.progress_pct for value in values] == [0.0, 50.0, 100.0]
        assert values[-1].finished is True
        assert uploader.latest_progress == values[-1]

    asyncio.run(run_test())


def test_invalid_progress_is_rejected() -> None:
    with pytest.raises(ValueError):
        MissionRawProgress.from_sdk(SimpleNamespace(current=3, total=2))


def test_plugin_contract_is_validated() -> None:
    with pytest.raises(TypeError):
        MissionRawUploader(object())
