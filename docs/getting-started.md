# Getting Started with aumai-toolemu

This guide takes you from a fresh install to a working test suite that emulates tool calls
without touching any real APIs.

---

## Prerequisites

- Python 3.11 or later
- `pip` (or your preferred package manager — `uv`, `poetry`, `pdm` all work)
- Optional: `fastapi` and `uvicorn` if you want to run the HTTP server mode

Verify your Python version:

```bash
python --version
# Python 3.11.x or higher
```

---

## Installation

### From PyPI (recommended)

```bash
pip install aumai-toolemu
```

Verify:

```bash
aumai-toolemu --version
```

### With HTTP server extras

```bash
pip install "aumai-toolemu[server]"
# or explicitly:
pip install aumai-toolemu fastapi uvicorn
```

### From source

```bash
git clone https://github.com/aumai/aumai-toolemu.git
cd aumai-toolemu
pip install -e .
```

### Development mode (with test/lint dependencies)

```bash
git clone https://github.com/aumai/aumai-toolemu.git
cd aumai-toolemu
pip install -e ".[dev]"
make test   # run test suite
make lint   # run ruff + mypy
```

---

## Your First Emulated Tool Call

This tutorial walks you through the core workflow: define a mock, run a call, and inspect the
result. No external services required.

### Step 1 — Define what your tool should return

The fundamental unit is a `MockResponse` — a status code plus a JSON body:

```python
from aumai_toolemu import MockResponse

# A successful search result
search_result = MockResponse(
    status_code=200,
    body={"results": ["Getting started with Python", "Python for beginners"]},
)

# An API error
error_result = MockResponse(
    status_code=503,
    body={"error": "Service temporarily unavailable"},
)
```

### Step 2 — Wrap the response in a ToolMock

A `ToolMock` groups responses under a tool name and controls how they are selected:

```python
from aumai_toolemu import ToolMock, MockBehavior

search_mock = ToolMock(
    tool_name="search",           # must match what your agent calls
    behavior=MockBehavior.static, # always return responses[0]
    responses=[search_result],
)
```

### Step 3 — Create the emulator

```python
from aumai_toolemu import ToolEmulator, EmulatorConfig

config = EmulatorConfig(
    mocks=[search_mock],
    record_calls=True,
)

emulator = ToolEmulator(config)
```

### Step 4 — Call the tool

```python
response = emulator.call("search", {"query": "Python tutorials"})

print(response.status_code)          # 200
print(response.body["results"][0])   # Getting started with Python
```

### Step 5 — Inspect the call record

```python
calls = emulator.get_recorded_calls()
print(len(calls))                    # 1
print(calls[0].tool_name)            # search
print(calls[0].input_data)           # {'query': 'Python tutorials'}
print(calls[0].timestamp)            # 2026-02-27T...+00:00
```

### Step 6 — Reset between tests

```python
emulator.reset()
print(emulator.get_recorded_calls())  # []
```

You now have a fully working emulator. Everything that follows builds on this foundation.

---

## Common Patterns

### Pattern 1 — Multi-step pagination with sequential responses

Model a paginated API where the agent must keep calling until it receives an empty page:

```python
from aumai_toolemu import (
    ToolEmulator, EmulatorConfig, ToolMock, MockResponse, MockBehavior,
)

emulator = ToolEmulator(
    EmulatorConfig(
        mocks=[
            ToolMock(
                tool_name="list_files",
                behavior=MockBehavior.sequential,
                responses=[
                    MockResponse(status_code=200, body={"files": ["a.txt", "b.txt"], "next": True}),
                    MockResponse(status_code=200, body={"files": ["c.txt"], "next": True}),
                    MockResponse(status_code=200, body={"files": [], "next": False}),
                ],
            )
        ]
    )
)

all_files: list[str] = []
while True:
    r = emulator.call("list_files", {"page": len(all_files)})
    all_files.extend(r.body["files"])
    if not r.body["next"]:
        break

assert all_files == ["a.txt", "b.txt", "c.txt"]
```

---

### Pattern 2 — Input-driven conditional responses

Return different data depending on what the agent sends:

```python
from aumai_toolemu import ToolMock, MockResponse, MockBehavior

# Return a cold response for London, fallback (sunny) for anything else
weather_mock = ToolMock(
    tool_name="get_weather",
    behavior=MockBehavior.conditional,
    conditions={"city": "London"},
    responses=[
        MockResponse(status_code=200, body={"temp": 8, "condition": "rainy"}),   # matches London
        MockResponse(status_code=200, body={"temp": 28, "condition": "sunny"}),  # fallback
    ],
)

emulator.add_mock(weather_mock)

r_london = emulator.call("get_weather", {"city": "London"})
r_other  = emulator.call("get_weather", {"city": "Sydney"})

assert r_london.body["condition"] == "rainy"
assert r_other.body["condition"] == "sunny"
```

---

### Pattern 3 — Chaos / resilience testing with error injection

Verify your agent retries correctly and handles failures without crashing:

```python
import random
from aumai_toolemu import ToolMock, MockResponse, MockBehavior

# The tool succeeds most of the time but fails 30 % of calls
flaky_mock = ToolMock(
    tool_name="external_api",
    behavior=MockBehavior.static,
    error_rate=0.3,
    responses=[MockResponse(status_code=200, body={"data": "ok"})],
)

emulator.add_mock(flaky_mock)

# Run 100 calls and count failures
results = [emulator.call("external_api", {}) for _ in range(100)]
failures = [r for r in results if r.status_code == 500]
successes = [r for r in results if r.status_code == 200]

# Roughly 30 % should be failures (probabilistic — do not assert exact count)
print(f"Failures: {len(failures)}, Successes: {len(successes)}")
```

---

### Pattern 4 — Latency simulation for timeout testing

Verify that your agent correctly times out when a tool responds too slowly:

```python
import time
from aumai_toolemu import ToolMock, MockResponse

slow_mock = ToolMock(
    tool_name="slow_database",
    responses=[
        MockResponse(
            status_code=200,
            body={"rows": []},
            latency_ms=2000.0,  # 2 seconds — should trigger your agent's timeout
        )
    ],
)

emulator.add_mock(slow_mock)

start = time.monotonic()
r = emulator.call("slow_database", {"query": "SELECT *"})
elapsed = time.monotonic() - start

assert elapsed >= 2.0
assert r.status_code == 200
```

---

### Pattern 5 — pytest fixture for test isolation

Encapsulate emulator setup in a pytest fixture so each test starts with a clean slate:

```python
import pytest
from aumai_toolemu import ToolEmulator, EmulatorConfig, ToolMock, MockResponse

@pytest.fixture
def emulator():
    """Provide a fresh ToolEmulator for each test."""
    config = EmulatorConfig(
        mocks=[
            ToolMock(
                tool_name="search",
                responses=[MockResponse(status_code=200, body={"results": ["r1"]})],
            ),
            ToolMock(
                tool_name="calculator",
                responses=[MockResponse(status_code=200, body={"result": 42})],
            ),
        ],
        record_calls=True,
    )
    emu = ToolEmulator(config)
    yield emu
    emu.reset()


def test_search_returns_results(emulator: ToolEmulator) -> None:
    r = emulator.call("search", {"query": "test"})
    assert r.status_code == 200
    assert "results" in r.body


def test_calculator_called_once(emulator: ToolEmulator) -> None:
    emulator.call("calculator", {"expression": "6 * 7"})
    calls = emulator.get_recorded_calls()
    assert len(calls) == 1
    assert calls[0].tool_name == "calculator"
```

---

## Troubleshooting FAQ

### `ToolNotFoundError: No mock registered for tool 'my_tool'`

Your agent (or test) called a tool that is not in the emulator's mock registry.

Solutions:
- Add a `ToolMock` with `tool_name="my_tool"` to your `EmulatorConfig.mocks` list.
- Use `emulator.add_mock(...)` at runtime before the call.
- Double-check spelling — tool names are matched exactly (case-sensitive).

---

### `ImportError: FastAPI is required for EmulatorServer`

You called `EmulatorServer` or `aumai-toolemu serve` without installing FastAPI.

```bash
pip install fastapi uvicorn
```

---

### `ImportError: uvicorn is required to run the emulator server`

FastAPI is installed but uvicorn is not.

```bash
pip install uvicorn
```

---

### My sequential mock is not cycling correctly

The sequence cursor is per-`ToolEmulator` instance and is only reset by calling `emulator.reset()`.
If you are reusing the emulator across tests, call `emulator.reset()` in your test teardown (or use
a fixture as shown in Pattern 5 above).

---

### The emulator does not simulate latency

Latency is applied only when `latency_ms > 0`. The `default_latency_ms` in `EmulatorConfig` is
used only when a `MockResponse` has `latency_ms = 0.0` (the default). To apply global latency:

```python
config = EmulatorConfig(
    default_latency_ms=100.0,  # 100 ms applied to all responses without their own latency
    mocks=[...],
)
```

---

### JSON decode error when using `--input` on the CLI

The `--input` value must be valid JSON. Wrap the JSON string in single quotes on Unix shells to
prevent the shell from interpreting the double quotes:

```bash
# Correct (Unix)
aumai-toolemu call --tool search --input '{"query": "python"}'

# Correct (Windows cmd)
aumai-toolemu call --tool search --input "{\"query\": \"python\"}"
```

---

### My config file fails to load

`EmulatorConfig` is validated by Pydantic at load time. Common mistakes:

- `error_rate` is outside 0.0–1.0
- `status_code` is outside 100–599
- `latency_ms` is negative
- `tool_name` is an empty string
- The YAML file is not valid YAML (check indentation)

Run `aumai-toolemu call --tool test --config your_file.yaml` to get a descriptive error message.
