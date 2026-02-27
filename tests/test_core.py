"""Comprehensive tests for aumai_toolemu core module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from aumai_toolemu.core import ToolEmulator, ToolNotFoundError
from aumai_toolemu.models import (
    EmulatorConfig,
    MockBehavior,
    MockResponse,
    RecordedCall,
    ToolMock,
)


# ---------------------------------------------------------------------------
# MockResponse model tests
# ---------------------------------------------------------------------------


class TestMockResponse:
    """Tests for the MockResponse model."""

    def test_create_default_response(self) -> None:
        response = MockResponse()
        assert response.status_code == 200
        assert response.body == {}
        assert response.latency_ms == 0.0

    def test_create_with_body(self) -> None:
        response = MockResponse(body={"result": "ok"})
        assert response.body == {"result": "ok"}

    def test_create_with_status_500(self) -> None:
        response = MockResponse(status_code=500)
        assert response.status_code == 500

    def test_invalid_status_code_below_100_raises(self) -> None:
        with pytest.raises(Exception):
            MockResponse(status_code=99)

    def test_invalid_status_code_above_599_raises(self) -> None:
        with pytest.raises(Exception):
            MockResponse(status_code=600)

    def test_valid_status_codes_boundary(self) -> None:
        MockResponse(status_code=100)
        MockResponse(status_code=599)

    def test_negative_latency_raises(self) -> None:
        with pytest.raises(Exception):
            MockResponse(latency_ms=-1.0)

    def test_zero_latency_valid(self) -> None:
        response = MockResponse(latency_ms=0.0)
        assert response.latency_ms == 0.0

    def test_headers_default_empty(self) -> None:
        response = MockResponse()
        assert response.headers == {}

    def test_headers_stored(self) -> None:
        response = MockResponse(headers={"content-type": "application/json"})
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.parametrize("code", [200, 201, 400, 404, 500, 503])
    def test_common_status_codes_valid(self, code: int) -> None:
        response = MockResponse(status_code=code)
        assert response.status_code == code


# ---------------------------------------------------------------------------
# ToolMock model tests
# ---------------------------------------------------------------------------


class TestToolMock:
    """Tests for the ToolMock model."""

    def test_create_minimal_mock(self) -> None:
        mock = ToolMock(tool_name="my_tool")
        assert mock.tool_name == "my_tool"
        assert mock.behavior == MockBehavior.static

    def test_empty_tool_name_raises(self) -> None:
        with pytest.raises(Exception):
            ToolMock(tool_name="")

    def test_whitespace_tool_name_raises(self) -> None:
        with pytest.raises(Exception):
            ToolMock(tool_name="   ")

    def test_tool_name_stripped(self) -> None:
        mock = ToolMock(tool_name="  my_tool  ")
        assert mock.tool_name == "my_tool"

    def test_invalid_error_rate_above_one_raises(self) -> None:
        with pytest.raises(Exception):
            ToolMock(tool_name="tool", error_rate=1.1)

    def test_invalid_error_rate_negative_raises(self) -> None:
        with pytest.raises(Exception):
            ToolMock(tool_name="tool", error_rate=-0.1)

    def test_valid_error_rate_boundary(self) -> None:
        mock = ToolMock(tool_name="tool", error_rate=1.0)
        assert mock.error_rate == 1.0
        mock2 = ToolMock(tool_name="tool2", error_rate=0.0)
        assert mock2.error_rate == 0.0

    def test_default_responses_empty(self) -> None:
        mock = ToolMock(tool_name="tool")
        assert mock.responses == []

    def test_default_conditions_none(self) -> None:
        mock = ToolMock(tool_name="tool")
        assert mock.conditions is None


# ---------------------------------------------------------------------------
# ToolEmulator static behavior tests
# ---------------------------------------------------------------------------


class TestToolEmulatorStatic:
    """Tests for ToolEmulator with static behavior mocks."""

    def test_call_returns_mock_response(self, emulator: ToolEmulator) -> None:
        response = emulator.call("static_tool", {})
        assert isinstance(response, MockResponse)

    def test_call_returns_correct_status_code(self, emulator: ToolEmulator) -> None:
        response = emulator.call("static_tool", {})
        assert response.status_code == 200

    def test_call_returns_correct_body(self, emulator: ToolEmulator) -> None:
        response = emulator.call("static_tool", {})
        assert response.body == {"result": "ok"}

    def test_call_unknown_tool_raises(self, emulator: ToolEmulator) -> None:
        with pytest.raises(ToolNotFoundError):
            emulator.call("nonexistent_tool", {})

    def test_tool_not_found_error_is_key_error(self) -> None:
        assert issubclass(ToolNotFoundError, KeyError)

    def test_static_always_returns_first_response(
        self, static_mock: ToolMock
    ) -> None:
        config = EmulatorConfig(mocks=[static_mock], record_calls=False)
        emulator = ToolEmulator(config)
        responses = [emulator.call("static_tool", {}) for _ in range(5)]
        assert all(r.body == {"result": "ok"} for r in responses)

    def test_call_records_call_when_enabled(self, emulator: ToolEmulator) -> None:
        emulator.call("static_tool", {"key": "value"})
        calls = emulator.get_recorded_calls()
        assert len(calls) == 1

    def test_call_records_tool_name(self, emulator: ToolEmulator) -> None:
        emulator.call("static_tool", {})
        calls = emulator.get_recorded_calls()
        assert calls[0].tool_name == "static_tool"

    def test_call_records_input_data(self, emulator: ToolEmulator) -> None:
        emulator.call("static_tool", {"foo": "bar"})
        calls = emulator.get_recorded_calls()
        assert calls[0].input_data == {"foo": "bar"}

    def test_call_records_response(self, emulator: ToolEmulator) -> None:
        emulator.call("static_tool", {})
        calls = emulator.get_recorded_calls()
        assert calls[0].response.status_code == 200

    def test_call_records_timestamp(self, emulator: ToolEmulator) -> None:
        emulator.call("static_tool", {})
        calls = emulator.get_recorded_calls()
        assert isinstance(calls[0].timestamp, datetime)

    def test_no_recording_when_disabled(
        self, no_record_emulator: ToolEmulator
    ) -> None:
        no_record_emulator.call("static_tool", {})
        calls = no_record_emulator.get_recorded_calls()
        assert len(calls) == 0

    def test_get_recorded_calls_returns_copy(self, emulator: ToolEmulator) -> None:
        emulator.call("static_tool", {})
        calls1 = emulator.get_recorded_calls()
        calls2 = emulator.get_recorded_calls()
        assert calls1 is not calls2

    def test_reset_clears_recorded_calls(self, emulator: ToolEmulator) -> None:
        emulator.call("static_tool", {})
        emulator.reset()
        assert emulator.get_recorded_calls() == []


# ---------------------------------------------------------------------------
# ToolEmulator sequential behavior tests
# ---------------------------------------------------------------------------


class TestToolEmulatorSequential:
    """Tests for sequential behavior mocks."""

    @pytest.fixture()
    def seq_emulator(self, sequential_mock: ToolMock) -> ToolEmulator:
        config = EmulatorConfig(mocks=[sequential_mock], record_calls=False)
        return ToolEmulator(config)

    def test_sequential_first_call(self, seq_emulator: ToolEmulator) -> None:
        response = seq_emulator.call("seq_tool", {})
        assert response.body == {"step": 1}

    def test_sequential_second_call(self, seq_emulator: ToolEmulator) -> None:
        seq_emulator.call("seq_tool", {})
        response = seq_emulator.call("seq_tool", {})
        assert response.body == {"step": 2}

    def test_sequential_third_call(self, seq_emulator: ToolEmulator) -> None:
        for _ in range(2):
            seq_emulator.call("seq_tool", {})
        response = seq_emulator.call("seq_tool", {})
        assert response.body == {"step": 3}

    def test_sequential_wraps_around(self, seq_emulator: ToolEmulator) -> None:
        for _ in range(3):
            seq_emulator.call("seq_tool", {})
        response = seq_emulator.call("seq_tool", {})
        assert response.body == {"step": 1}

    def test_reset_resets_sequence_position(self, seq_emulator: ToolEmulator) -> None:
        seq_emulator.call("seq_tool", {})
        seq_emulator.call("seq_tool", {})
        seq_emulator.reset()
        response = seq_emulator.call("seq_tool", {})
        assert response.body == {"step": 1}


# ---------------------------------------------------------------------------
# ToolEmulator error behavior tests
# ---------------------------------------------------------------------------


class TestToolEmulatorError:
    """Tests for error behavior mocks."""

    @pytest.fixture()
    def err_emulator(self, error_mock: ToolMock) -> ToolEmulator:
        config = EmulatorConfig(mocks=[error_mock], record_calls=False)
        return ToolEmulator(config)

    def test_error_behavior_returns_500(self, err_emulator: ToolEmulator) -> None:
        response = err_emulator.call("error_tool", {})
        assert response.status_code == 500

    def test_error_behavior_body_has_error_key(
        self, err_emulator: ToolEmulator
    ) -> None:
        response = err_emulator.call("error_tool", {})
        assert "error" in response.body

    def test_error_behavior_always_500(self, err_emulator: ToolEmulator) -> None:
        for _ in range(5):
            response = err_emulator.call("error_tool", {})
            assert response.status_code == 500


# ---------------------------------------------------------------------------
# ToolEmulator random behavior tests
# ---------------------------------------------------------------------------


class TestToolEmulatorRandom:
    """Tests for random behavior mocks."""

    @pytest.fixture()
    def rand_emulator(self, random_mock: ToolMock) -> ToolEmulator:
        config = EmulatorConfig(mocks=[random_mock], record_calls=False)
        return ToolEmulator(config)

    def test_random_returns_valid_response(self, rand_emulator: ToolEmulator) -> None:
        response = rand_emulator.call("rand_tool", {})
        assert response.status_code == 200

    def test_random_response_from_pool(self, rand_emulator: ToolEmulator) -> None:
        valid_bodies = [{"value": "a"}, {"value": "b"}]
        for _ in range(20):
            response = rand_emulator.call("rand_tool", {})
            assert response.body in valid_bodies


# ---------------------------------------------------------------------------
# ToolEmulator conditional behavior tests
# ---------------------------------------------------------------------------


class TestToolEmulatorConditional:
    """Tests for conditional behavior mocks."""

    @pytest.fixture()
    def cond_emulator(self, conditional_mock: ToolMock) -> ToolEmulator:
        config = EmulatorConfig(mocks=[conditional_mock], record_calls=False)
        return ToolEmulator(config)

    def test_matching_condition_returns_first_response(
        self, cond_emulator: ToolEmulator
    ) -> None:
        response = cond_emulator.call("cond_tool", {"env": "production"})
        assert response.body == {"environment": "prod"}

    def test_non_matching_condition_returns_last_response(
        self, cond_emulator: ToolEmulator
    ) -> None:
        response = cond_emulator.call("cond_tool", {"env": "staging"})
        assert response.body == {"environment": "other"}

    def test_empty_input_returns_last_response(
        self, cond_emulator: ToolEmulator
    ) -> None:
        response = cond_emulator.call("cond_tool", {})
        assert response.body == {"environment": "other"}


# ---------------------------------------------------------------------------
# ToolEmulator error injection tests
# ---------------------------------------------------------------------------


class TestToolEmulatorErrorInjection:
    """Tests for probabilistic error injection."""

    def test_error_rate_1_always_injects(self) -> None:
        mock = ToolMock(
            tool_name="tool",
            behavior=MockBehavior.static,
            error_rate=1.0,
            responses=[MockResponse(status_code=200, body={"ok": True})],
        )
        config = EmulatorConfig(mocks=[mock], record_calls=False)
        emulator = ToolEmulator(config)
        for _ in range(5):
            response = emulator.call("tool", {})
            assert response.status_code == 500

    def test_error_rate_0_never_injects(self) -> None:
        mock = ToolMock(
            tool_name="tool",
            behavior=MockBehavior.static,
            error_rate=0.0,
            responses=[MockResponse(status_code=200, body={"ok": True})],
        )
        config = EmulatorConfig(mocks=[mock], record_calls=False)
        emulator = ToolEmulator(config)
        for _ in range(10):
            response = emulator.call("tool", {})
            assert response.status_code == 200


# ---------------------------------------------------------------------------
# ToolEmulator add_mock tests
# ---------------------------------------------------------------------------


class TestToolEmulatorAddMock:
    """Tests for add_mock method."""

    def test_add_mock_registers_new_tool(self, emulator: ToolEmulator) -> None:
        new_mock = ToolMock(
            tool_name="new_tool",
            behavior=MockBehavior.static,
            responses=[MockResponse(status_code=201, body={"created": True})],
        )
        emulator.add_mock(new_mock)
        response = emulator.call("new_tool", {})
        assert response.status_code == 201

    def test_add_mock_replaces_existing(self, emulator: ToolEmulator) -> None:
        replacement = ToolMock(
            tool_name="static_tool",
            behavior=MockBehavior.static,
            responses=[MockResponse(status_code=418, body={"replaced": True})],
        )
        emulator.add_mock(replacement)
        response = emulator.call("static_tool", {})
        assert response.status_code == 418


# ---------------------------------------------------------------------------
# ToolEmulator latency tests
# ---------------------------------------------------------------------------


class TestToolEmulatorLatency:
    """Tests for latency simulation (patched to avoid actual sleeping)."""

    def test_response_latency_used_when_nonzero(self) -> None:
        mock = ToolMock(
            tool_name="latency_tool",
            behavior=MockBehavior.static,
            responses=[MockResponse(status_code=200, body={}, latency_ms=100.0)],
        )
        config = EmulatorConfig(mocks=[mock], record_calls=False)
        emulator = ToolEmulator(config)
        with patch("aumai_toolemu.core.time.sleep") as mock_sleep:
            emulator.call("latency_tool", {})
            mock_sleep.assert_called_once()
            called_with = mock_sleep.call_args[0][0]
            assert abs(called_with - 0.1) < 0.001  # 100ms = 0.1s

    def test_default_latency_used_when_response_latency_zero(self) -> None:
        mock = ToolMock(
            tool_name="tool",
            behavior=MockBehavior.static,
            responses=[MockResponse(status_code=200, body={}, latency_ms=0.0)],
        )
        config = EmulatorConfig(mocks=[mock], record_calls=False, default_latency_ms=50.0)
        emulator = ToolEmulator(config)
        with patch("aumai_toolemu.core.time.sleep") as mock_sleep:
            emulator.call("tool", {})
            mock_sleep.assert_called_once()
            called_with = mock_sleep.call_args[0][0]
            assert abs(called_with - 0.05) < 0.001

    def test_no_sleep_when_latency_zero_and_no_default(self, emulator: ToolEmulator) -> None:
        with patch("aumai_toolemu.core.time.sleep") as mock_sleep:
            emulator.call("static_tool", {})
            mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# EmulatorConfig tests
# ---------------------------------------------------------------------------


class TestEmulatorConfig:
    """Tests for the EmulatorConfig model."""

    def test_create_empty_config(self) -> None:
        config = EmulatorConfig()
        assert config.mocks == []
        assert config.default_latency_ms == 0.0
        assert config.record_calls is True

    def test_record_calls_default_true(self) -> None:
        config = EmulatorConfig()
        assert config.record_calls is True

    def test_multiple_mocks(self, static_mock: ToolMock, error_mock: ToolMock) -> None:
        config = EmulatorConfig(mocks=[static_mock, error_mock])
        assert len(config.mocks) == 2


# ---------------------------------------------------------------------------
# RecordedCall model tests
# ---------------------------------------------------------------------------


class TestRecordedCall:
    """Tests for the RecordedCall model."""

    def test_create_recorded_call(self, ok_response: MockResponse) -> None:
        call = RecordedCall(
            tool_name="test_tool",
            input_data={"key": "value"},
            response=ok_response,
            timestamp=datetime.now(tz=timezone.utc),
        )
        assert call.tool_name == "test_tool"
        assert call.input_data == {"key": "value"}

    def test_model_dump_json(self, ok_response: MockResponse) -> None:
        call = RecordedCall(
            tool_name="test_tool",
            input_data={},
            response=ok_response,
            timestamp=datetime.now(tz=timezone.utc),
        )
        data = call.model_dump(mode="json")
        assert data["tool_name"] == "test_tool"


# ---------------------------------------------------------------------------
# Multi-tool emulator tests
# ---------------------------------------------------------------------------


class TestMultiToolEmulator:
    """Tests with multiple mocks registered."""

    def test_multiple_tools_callable(
        self, multi_mock_config: EmulatorConfig
    ) -> None:
        emulator = ToolEmulator(multi_mock_config)
        static_response = emulator.call("static_tool", {})
        error_response = emulator.call("error_tool", {})
        assert static_response.status_code == 200
        assert error_response.status_code == 500

    def test_recorded_calls_across_tools(
        self, multi_mock_config: EmulatorConfig
    ) -> None:
        emulator = ToolEmulator(multi_mock_config)
        emulator.call("static_tool", {})
        emulator.call("error_tool", {})
        calls = emulator.get_recorded_calls()
        assert len(calls) == 2

    def test_sequence_positions_per_tool(
        self, multi_mock_config: EmulatorConfig
    ) -> None:
        emulator = ToolEmulator(multi_mock_config)
        r1 = emulator.call("seq_tool", {})
        r2 = emulator.call("seq_tool", {})
        assert r1.body != r2.body


# ---------------------------------------------------------------------------
# Hypothesis-based property tests
# ---------------------------------------------------------------------------


@given(
    status_code=st.integers(min_value=100, max_value=599),
    latency_ms=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
)
@settings(max_examples=30)
def test_mock_response_valid_inputs_never_raise(
    status_code: int, latency_ms: float
) -> None:
    """MockResponse with valid ranges should never raise."""
    response = MockResponse(status_code=status_code, latency_ms=latency_ms)
    assert response.status_code == status_code


@given(
    error_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
@settings(max_examples=30)
def test_tool_mock_valid_error_rate_never_raises(error_rate: float) -> None:
    """ToolMock with error_rate in [0, 1] should not raise."""
    mock = ToolMock(tool_name="test_tool", error_rate=error_rate)
    assert mock.error_rate == error_rate
