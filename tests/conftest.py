"""Shared pytest fixtures for aumai-toolemu tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from aumai_toolemu.core import ToolEmulator
from aumai_toolemu.models import (
    EmulatorConfig,
    MockBehavior,
    MockResponse,
    ToolMock,
)


# ---------------------------------------------------------------------------
# MockResponse fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ok_response() -> MockResponse:
    """A basic 200 OK response with no latency."""
    return MockResponse(status_code=200, body={"result": "ok"})


@pytest.fixture()
def error_response() -> MockResponse:
    """A 500 error response."""
    return MockResponse(status_code=500, body={"error": "server_error"})


@pytest.fixture()
def response_with_latency() -> MockResponse:
    """A 200 response that declares latency (not actually slept in unit tests)."""
    return MockResponse(status_code=200, body={"data": 1}, latency_ms=10.0)


# ---------------------------------------------------------------------------
# ToolMock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def static_mock(ok_response: MockResponse) -> ToolMock:
    """A static mock that always returns *ok_response*."""
    return ToolMock(
        tool_name="static_tool",
        behavior=MockBehavior.static,
        responses=[ok_response],
    )


@pytest.fixture()
def sequential_mock() -> ToolMock:
    """A sequential mock with three distinct responses."""
    return ToolMock(
        tool_name="seq_tool",
        behavior=MockBehavior.sequential,
        responses=[
            MockResponse(status_code=200, body={"step": 1}),
            MockResponse(status_code=200, body={"step": 2}),
            MockResponse(status_code=201, body={"step": 3}),
        ],
    )


@pytest.fixture()
def random_mock() -> ToolMock:
    """A random-behavior mock with two responses."""
    return ToolMock(
        tool_name="rand_tool",
        behavior=MockBehavior.random,
        responses=[
            MockResponse(status_code=200, body={"value": "a"}),
            MockResponse(status_code=200, body={"value": "b"}),
        ],
    )


@pytest.fixture()
def error_mock() -> ToolMock:
    """A mock permanently stuck in the error behavior."""
    return ToolMock(
        tool_name="error_tool",
        behavior=MockBehavior.error,
        responses=[MockResponse(status_code=200, body={})],
    )


@pytest.fixture()
def conditional_mock() -> ToolMock:
    """A conditional mock that matches on the 'env' key."""
    return ToolMock(
        tool_name="cond_tool",
        behavior=MockBehavior.conditional,
        conditions={"env": "production"},
        responses=[
            MockResponse(status_code=200, body={"environment": "prod"}),
            MockResponse(status_code=200, body={"environment": "other"}),
        ],
    )


# ---------------------------------------------------------------------------
# EmulatorConfig / ToolEmulator fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_config(static_mock: ToolMock) -> EmulatorConfig:
    """Config with a single static mock and recording enabled."""
    return EmulatorConfig(mocks=[static_mock], record_calls=True)


@pytest.fixture()
def multi_mock_config(
    static_mock: ToolMock,
    sequential_mock: ToolMock,
    error_mock: ToolMock,
) -> EmulatorConfig:
    """Config with several mock tools registered."""
    return EmulatorConfig(
        mocks=[static_mock, sequential_mock, error_mock],
        record_calls=True,
    )


@pytest.fixture()
def emulator(minimal_config: EmulatorConfig) -> ToolEmulator:
    """A ToolEmulator built from the minimal config."""
    return ToolEmulator(minimal_config)


@pytest.fixture()
def no_record_emulator(static_mock: ToolMock) -> ToolEmulator:
    """A ToolEmulator with call recording disabled."""
    config = EmulatorConfig(mocks=[static_mock], record_calls=False)
    return ToolEmulator(config)


# ---------------------------------------------------------------------------
# File-based config fixtures (YAML & JSON)
# ---------------------------------------------------------------------------


def _minimal_config_dict() -> dict[str, Any]:
    """Return a raw dict representing a minimal config."""
    return {
        "default_latency_ms": 0.0,
        "record_calls": True,
        "mocks": [
            {
                "tool_name": "ping",
                "behavior": "static",
                "error_rate": 0.0,
                "responses": [
                    {
                        "status_code": 200,
                        "latency_ms": 0.0,
                        "body": {"pong": True},
                        "headers": {},
                    }
                ],
            }
        ],
    }


@pytest.fixture()
def yaml_config_file(tmp_path: Path) -> Path:
    """A temporary YAML config file."""
    config_path = tmp_path / "mocks.yaml"
    config_path.write_text(
        yaml.dump(_minimal_config_dict(), default_flow_style=False),
        encoding="utf-8",
    )
    return config_path


@pytest.fixture()
def json_config_file(tmp_path: Path) -> Path:
    """A temporary JSON config file."""
    config_path = tmp_path / "mocks.json"
    config_path.write_text(
        json.dumps(_minimal_config_dict()),
        encoding="utf-8",
    )
    return config_path


@pytest.fixture()
def tmp_output_dir(tmp_path: Path) -> Path:
    """A clean temporary directory for CLI output tests."""
    return tmp_path
