"""AumAI ToolEmu — mock tool execution engine for agent testing."""

from aumai_toolemu.core import EmulatorServer, ToolEmulator, ToolNotFoundError
from aumai_toolemu.models import (
    EmulatorConfig,
    MockBehavior,
    MockResponse,
    RecordedCall,
    ToolMock,
)

__version__ = "0.1.0"

__all__ = [
    "ToolEmulator",
    "EmulatorServer",
    "ToolNotFoundError",
    "EmulatorConfig",
    "MockBehavior",
    "MockResponse",
    "RecordedCall",
    "ToolMock",
]
