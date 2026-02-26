"""Pydantic models for aumai-toolemu."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class MockResponse(BaseModel):
    """A single canned response returned by the emulator."""

    status_code: int = Field(default=200, description="HTTP-style status code")
    body: dict[str, object] = Field(
        default_factory=dict, description="JSON-serialisable response body"
    )
    latency_ms: float = Field(
        default=0.0, description="Simulated response latency in milliseconds"
    )
    headers: dict[str, str] = Field(
        default_factory=dict, description="HTTP-style response headers"
    )

    @field_validator("status_code")
    @classmethod
    def status_code_must_be_valid(cls, value: int) -> int:
        """Ensure status code is in a sensible range."""
        if not (100 <= value <= 599):
            raise ValueError(f"status_code must be 100-599, got {value}")
        return value

    @field_validator("latency_ms")
    @classmethod
    def latency_must_be_non_negative(cls, value: float) -> float:
        """Ensure latency is non-negative."""
        if value < 0:
            raise ValueError(f"latency_ms must be >= 0, got {value}")
        return value


class MockBehavior(str, Enum):
    """Controls how the emulator cycles through responses."""

    static = "static"          # Always return responses[0]
    sequential = "sequential"  # Cycle through responses in order
    random = "random"          # Pick a random response
    error = "error"            # Always raise an error / return 500
    conditional = "conditional"  # Match on input conditions


class ToolMock(BaseModel):
    """Configuration for a single mocked tool."""

    tool_name: str = Field(description="Identifier matching the tool being mocked")
    behavior: MockBehavior = Field(
        default=MockBehavior.static, description="Response selection strategy"
    )
    responses: list[MockResponse] = Field(
        default_factory=list, description="Pool of possible responses"
    )
    error_rate: float = Field(
        default=0.0,
        description="Probability (0.0-1.0) of injecting a random error",
    )
    conditions: dict[str, object] | None = Field(
        default=None,
        description="Key-value conditions used when behavior=conditional",
    )

    @field_validator("error_rate")
    @classmethod
    def error_rate_must_be_fraction(cls, value: float) -> float:
        """Clamp error_rate to [0, 1]."""
        if not (0.0 <= value <= 1.0):
            raise ValueError(f"error_rate must be between 0.0 and 1.0, got {value}")
        return value

    @field_validator("tool_name")
    @classmethod
    def tool_name_must_not_be_empty(cls, value: str) -> str:
        """Ensure tool_name is non-empty."""
        if not value.strip():
            raise ValueError("tool_name must not be empty")
        return value.strip()


class EmulatorConfig(BaseModel):
    """Top-level configuration for a ToolEmulator instance."""

    mocks: list[ToolMock] = Field(
        default_factory=list, description="All configured tool mocks"
    )
    default_latency_ms: float = Field(
        default=0.0, description="Fallback latency applied when a mock has none set"
    )
    record_calls: bool = Field(
        default=True, description="Whether to record all calls for later inspection"
    )


class RecordedCall(BaseModel):
    """A single recorded tool invocation."""

    tool_name: str = Field(description="Name of the tool that was called")
    input_data: dict[str, object] = Field(description="Input payload supplied by the caller")
    response: MockResponse = Field(description="Response that was returned")
    timestamp: datetime = Field(description="UTC timestamp of the call")


__all__ = [
    "MockResponse",
    "MockBehavior",
    "ToolMock",
    "EmulatorConfig",
    "RecordedCall",
]
