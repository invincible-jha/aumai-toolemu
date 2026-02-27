"""Core logic for aumai-toolemu: emulator engine and FastAPI server."""

from __future__ import annotations

import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from aumai_toolemu.models import (
    EmulatorConfig,
    MockBehavior,
    MockResponse,
    RecordedCall,
    ToolMock,
)


class ToolNotFoundError(KeyError):
    """Raised when the emulator has no mock registered for a tool name."""


class ToolEmulator:
    """Emulate tool calls using pre-configured mock responses.

    Args:
        config: :class:`EmulatorConfig` describing all mock behaviours.
    """

    def __init__(self, config: EmulatorConfig) -> None:
        self._config = config
        self._mocks: dict[str, ToolMock] = {m.tool_name: m for m in config.mocks}
        # Sequential cursor per tool.
        self._sequence_positions: dict[str, int] = {}
        self._recorded_calls: list[RecordedCall] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def call(self, tool_name: str, input_data: dict[str, object]) -> MockResponse:
        """Execute a mocked tool call and return the configured response.

        Simulates latency if configured.  Records the call when
        ``record_calls`` is True.

        Args:
            tool_name: The identifier of the tool to invoke.
            input_data: Arbitrary input payload.

        Returns:
            The :class:`MockResponse` for this invocation.

        Raises:
            ToolNotFoundError: When no mock is registered for *tool_name*.
        """
        mock = self._mocks.get(tool_name)
        if mock is None:
            raise ToolNotFoundError(f"No mock registered for tool '{tool_name}'")

        response = self._select_response(mock, input_data)
        latency = response.latency_ms if response.latency_ms > 0 else self._config.default_latency_ms

        if latency > 0:
            time.sleep(latency / 1000.0)

        if self._config.record_calls:
            self._recorded_calls.append(
                RecordedCall(
                    tool_name=tool_name,
                    input_data=input_data,
                    response=response,
                    timestamp=datetime.now(tz=timezone.utc),
                )
            )

        return response

    def get_recorded_calls(self) -> list[RecordedCall]:
        """Return a copy of all recorded calls."""
        return list(self._recorded_calls)

    def reset(self) -> None:
        """Clear recorded calls and reset sequence positions."""
        self._recorded_calls.clear()
        self._sequence_positions.clear()

    def add_mock(self, mock: ToolMock) -> None:
        """Register or replace a mock at runtime."""
        self._mocks[mock.tool_name] = mock

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_response(
        self, mock: ToolMock, input_data: dict[str, object]
    ) -> MockResponse:
        """Choose the appropriate response based on the mock's behaviour."""
        # Probabilistic error injection overrides everything.
        if mock.error_rate > 0 and random.random() < mock.error_rate:
            return MockResponse(
                status_code=500,
                body={"error": "injected_error", "tool": mock.tool_name},
            )

        if mock.behavior == MockBehavior.error:
            return MockResponse(
                status_code=500,
                body={"error": "tool_error", "tool": mock.tool_name},
            )

        if not mock.responses:
            return MockResponse(status_code=200, body={})

        if mock.behavior == MockBehavior.static:
            return mock.responses[0]

        if mock.behavior == MockBehavior.sequential:
            pos = self._sequence_positions.get(mock.tool_name, 0)
            response = mock.responses[pos % len(mock.responses)]
            self._sequence_positions[mock.tool_name] = pos + 1
            return response

        if mock.behavior == MockBehavior.random:
            return random.choice(mock.responses)

        if mock.behavior == MockBehavior.conditional:
            return self._match_conditional(mock, input_data)

        # Fallback.
        return mock.responses[0]

    def _match_conditional(
        self, mock: ToolMock, input_data: dict[str, object]
    ) -> MockResponse:
        """Return the first response whose conditions all match input_data.

        Falls back to the last response (or a default 200) if no match.
        """
        if mock.conditions is None or not mock.responses:
            return mock.responses[0] if mock.responses else MockResponse(status_code=200, body={})

        for response in mock.responses:
            matched = all(
                input_data.get(k) == v for k, v in mock.conditions.items()
            )
            if matched:
                return response

        # Default: return the last response.
        return mock.responses[-1]


# ---------------------------------------------------------------------------
# FastAPI emulator server
# ---------------------------------------------------------------------------


def _build_fastapi_app(emulator: ToolEmulator) -> Any:
    """Construct and return a FastAPI application wrapping *emulator*.

    Import is deferred so the module loads without fastapi when it's not
    installed (e.g. when only using the emulator programmatically).
    """
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise ImportError(
            "FastAPI is required for EmulatorServer. "
            "Install it with: pip install fastapi uvicorn"
        ) from exc

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        yield

    app = FastAPI(title="AumAI Tool Emulator", lifespan=lifespan)

    @app.post("/tools/{tool_name}")
    async def call_tool(tool_name: str, body: dict[str, object] | None = None) -> JSONResponse:
        """Emulate a tool call."""
        input_data: dict[str, object] = body or {}
        try:
            response = emulator.call(tool_name, input_data)
        except ToolNotFoundError:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not registered")
        return JSONResponse(
            content=response.body,
            status_code=response.status_code,
            headers=response.headers,
        )

    @app.get("/calls")
    async def get_calls() -> list[dict[str, object]]:
        """Return all recorded calls."""
        return [call.model_dump(mode="json") for call in emulator.get_recorded_calls()]

    @app.delete("/calls")
    async def reset_calls() -> dict[str, str]:
        """Clear recorded calls."""
        emulator.reset()
        return {"status": "reset"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


class EmulatorServer:
    """FastAPI-based HTTP server that emulates tool endpoints.

    By default the server binds only to localhost (``127.0.0.1``) so it is
    not reachable from other machines.  Pass ``host="0.0.0.0"`` explicitly
    when you need the server to accept external connections.

    Usage::

        server = EmulatorServer(config)
        server.run(port=9000)  # binds to 127.0.0.1:9000 by default

        # Expose to the network explicitly:
        server.run(host="0.0.0.0", port=9000)
    """

    def __init__(self, config: EmulatorConfig) -> None:
        self._emulator = ToolEmulator(config)
        self._app = _build_fastapi_app(self._emulator)

    @property
    def app(self) -> Any:
        """Return the underlying FastAPI application instance."""
        return self._app

    def run(self, host: str = "127.0.0.1", port: int = 9000) -> None:
        """Start the emulator HTTP server (blocking).

        Args:
            host: Interface to bind to.  Defaults to ``"127.0.0.1"`` (localhost
                only).  Pass ``"0.0.0.0"`` to listen on all interfaces.
            port: TCP port to listen on.  Defaults to ``9000``.
        """
        try:
            import uvicorn
        except ImportError as exc:
            raise ImportError(
                "uvicorn is required to run the emulator server. "
                "Install it with: pip install uvicorn"
            ) from exc
        uvicorn.run(self._app, host=host, port=port)


__all__ = [
    "ToolEmulator",
    "ToolNotFoundError",
    "EmulatorServer",
]
