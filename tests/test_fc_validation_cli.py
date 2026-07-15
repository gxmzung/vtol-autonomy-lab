import pytest

from src.fc_validation_cli import parse_arguments


def test_cli_parses_safe_upload_options() -> None:
    args = parse_arguments(
        [
            "--connection-url",
            "serial://COM5:57600",
            "--upload",
            "--keep-existing",
            "--settle-time",
            "0.5",
        ]
    )

    assert args.connection_url == "serial://COM5:57600"
    assert args.upload is True
    assert args.keep_existing is True
    assert args.settle_time == 0.5


def test_cli_requires_connection_url() -> None:
    with pytest.raises(SystemExit):
        parse_arguments([])
