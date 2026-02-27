# API Reference — aumai-toolemu

Complete reference for all public classes, functions, and models exposed by `aumai-toolemu`.

---

## Module `aumai_toolemu`

The package re-exports all public symbols from `core` and `models` at the top level.

```python
from aumai_toolemu import (
    # Core
    ToolEmulator,
    EmulatorServer,
    ToolNotFoundError,
    # Models
    EmulatorConfig,
    MockBehavior,
    MockResponse,
    RecordedCall,
    ToolMock,
)
```

**Package version:** `aumai_toolemu.__version__` (`str`)

---

## Module `aumai_toolemu.core`

Contains the emulator engine and the optional HTTP server wrapper.

---

### `ToolEmulator`

```python
class ToolEmulator:
    def __init__(self, config: EmulatorConfig) -> None: ...
```

The primary class. Executes mock tool calls using pre-configured `ToolMock` definitions.

**Constructor parameters:**

| Parameter | Type | Description |
|---|---|---|
| `config` | `EmulatorConfig` | Top-level configuration describing all mocks and global options |

**Example:**

```python
from aumai_toolemu import ToolEmulator, EmulatorConfig, ToolMock, MockResponse

emulator = ToolEmulator(
    EmulatorConfig(
        mocks=[
            ToolMock(
                tool_name="search",
                responses=[MockResponse(status_code=200, body={"results": ["x"]})],
            )
        ]
    )
)
```

---

#### `ToolEmulator.call`

```python
def call(
    self,
    tool_name: str,
    input_data: dict[str, object],
) -> MockResponse:
```

Execute a mocked tool call and return the configured response.

Simulates latency via `time.sleep` if configured. Records the call when `record_calls` is `True`.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `tool_name` | `str` | The identifier of the tool to invoke. Must match a registered `ToolMock.tool_name`. |
| `input_data` | `dict[str, object]` | Arbitrary input payload passed to conditional matching and recorded in call history. |

**Returns:** `MockResponse` — the selected response for this invocation.

**Raises:** `ToolNotFoundError` — when no mock is registered for `tool_name`.

**Example:**

```python
response = emulator.call("search", {"query": "cats", "limit": 10})
assert response.status_code == 200
```

---

#### `ToolEmulator.get_recorded_calls`

```python
def get_recorded_calls(self) -> list[RecordedCall]:
```

Return a shallow copy of all recorded calls since the emulator was created or last reset.

**Returns:** `list[RecordedCall]` — ordered by call time, oldest first.

**Example:**

```python
calls = emulator.get_recorded_calls()
for call in calls:
    print(call.tool_name, call.input_data, call.timestamp)
```

---

#### `ToolEmulator.reset`

```python
def reset(self) -> None:
```

Clear all recorded calls and reset all sequential mock cursors back to position 0.

This method has no return value. Call it in test teardown to ensure test isolation.

**Example:**

```python
emulator.reset()
assert emulator.get_recorded_calls() == []
```

---

#### `ToolEmulator.add_mock`

```python
def add_mock(self, mock: ToolMock) -> None:
```

Register a new mock, or replace an existing one with the same `tool_name`, at runtime.

Useful for dynamically adjusting the emulator's behavior within a test without rebuilding the
entire `EmulatorConfig`.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `mock` | `ToolMock` | The new or replacement mock definition |

**Example:**

```python
from aumai_toolemu import ToolMock, MockResponse

emulator.add_mock(
    ToolMock(
        tool_name="send_email",
        responses=[MockResponse(status_code=200, body={"sent": True})],
    )
)
r = emulator.call("send_email", {"to": "user@example.com", "subject": "Hello"})
assert r.body["sent"] is True
```

---

### `ToolNotFoundError`

```python
class ToolNotFoundError(KeyError): ...
```

Raised by `ToolEmulator.call()` when no mock is registered for the requested tool name.

Inherits from `KeyError` so it can be caught with either `ToolNotFoundError` or `KeyError`.

**Example:**

```python
from aumai_toolemu import ToolNotFoundError

try:
    emulator.call("unregistered_tool", {})
except ToolNotFoundError as exc:
    print(f"Tool not found: {exc}")
```

---

### `EmulatorServer`

```python
class EmulatorServer:
    def __init__(self, config: EmulatorConfig) -> None: ...
```

FastAPI-based HTTP server that exposes a `ToolEmulator` over HTTP. Requires `fastapi` and
`uvicorn` to be installed.

By default the server binds to `127.0.0.1` (localhost only). Pass `host="0.0.0.0"` to `run()`
when you need external connectivity.

**Constructor parameters:**

| Parameter | Type | Description |
|---|---|---|
| `config` | `EmulatorConfig` | Passed directly to the underlying `ToolEmulator` |

**Example:**

```python
from aumai_toolemu import EmulatorServer, EmulatorConfig

server = EmulatorServer(config)
```

---

#### `EmulatorServer.app`

```python
@property
def app(self) -> Any:
```

Returns the underlying FastAPI application instance. Use this for ASGI-level testing with
`httpx.AsyncClient` and `httpx.ASGITransport` — no listening port required.

**Returns:** `fastapi.FastAPI` instance.

**Example:**

```python
import httpx

async def test_health():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app),
        base_url="http://test",
    ) as client:
        r = await client.get("/health")
        assert r.json() == {"status": "ok"}
```

---

#### `EmulatorServer.run`

```python
def run(self, host: str = "127.0.0.1", port: int = 9000) -> None:
```

Start the HTTP server. This call is **blocking** — it does not return until the process is
interrupted.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `host` | `str` | `"127.0.0.1"` | Interface to bind. Use `"0.0.0.0"` for all interfaces. |
| `port` | `int` | `9000` | TCP port to listen on. |

**Raises:** `ImportError` — if `uvicorn` is not installed.

**Example:**

```python
server.run(host="127.0.0.1", port=9000)
```

---

## Module `aumai_toolemu.models`

All Pydantic models. Every field is validated at construction time; invalid values raise
`pydantic.ValidationError`.

---

### `MockResponse`

```python
class MockResponse(BaseModel):
    status_code: int = 200
    body: dict[str, object] = {}
    latency_ms: float = 0.0
    headers: dict[str, str] = {}
```

A single canned response returned by the emulator.

**Fields:**

| Field | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `status_code` | `int` | `200` | 100–599 | HTTP-style status code. Values outside this range raise `ValidationError`. |
| `body` | `dict[str, object]` | `{}` | Must be JSON-serializable | Response payload returned to the caller. |
| `latency_ms` | `float` | `0.0` | >= 0 | Simulated latency in milliseconds. Set to 0 to use `EmulatorConfig.default_latency_ms`. |
| `headers` | `dict[str, str]` | `{}` | — | HTTP-style headers, returned as response headers in server mode. |

**Validation errors:**
- `status_code` outside 100–599 → `ValueError: status_code must be 100-599`
- `latency_ms` < 0 → `ValueError: latency_ms must be >= 0`

**Example:**

```python
from aumai_toolemu import MockResponse

# A fast success
resp = MockResponse(status_code=200, body={"ok": True}, latency_ms=10.0)

# A slow error with headers
resp = MockResponse(
    status_code=503,
    body={"error": "Service Unavailable"},
    latency_ms=5000.0,
    headers={"Retry-After": "30"},
)
```

---

### `MockBehavior`

```python
class MockBehavior(str, Enum):
    static = "static"
    sequential = "sequential"
    random = "random"
    error = "error"
    conditional = "conditional"
```

Controls how `ToolEmulator` selects a response from a `ToolMock`'s `responses` list.

| Value | Selection logic |
|---|---|
| `static` | Always return `responses[0]`. |
| `sequential` | Maintain a per-tool cursor. Return `responses[cursor % len(responses)]`, increment cursor. |
| `random` | Return `random.choice(responses)`. |
| `error` | Always return a synthetic `MockResponse(status_code=500)`. |
| `conditional` | Iterate `responses`. For the first response where all `mock.conditions` match `input_data`, return it. Fall back to `responses[-1]`. |

---

### `ToolMock`

```python
class ToolMock(BaseModel):
    tool_name: str
    behavior: MockBehavior = MockBehavior.static
    responses: list[MockResponse] = []
    error_rate: float = 0.0
    conditions: dict[str, object] | None = None
```

Configuration for a single mocked tool.

**Fields:**

| Field | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `tool_name` | `str` | required | Non-empty after stripping | Identifier matching the tool being mocked. Must match what your agent passes to `call()`. |
| `behavior` | `MockBehavior` | `static` | Enum value | Response selection strategy. |
| `responses` | `list[MockResponse]` | `[]` | — | Pool of possible responses. |
| `error_rate` | `float` | `0.0` | 0.0–1.0 | Probability of injecting a random 500 error. Checked before any behavior-based selection. |
| `conditions` | `dict[str, object] \| None` | `None` | — | Key-value conditions for `conditional` behavior. All keys must match `input_data` for a response to be selected. |

**Validation errors:**
- `error_rate` outside 0.0–1.0 → `ValueError: error_rate must be between 0.0 and 1.0`
- `tool_name` is empty or whitespace-only → `ValueError: tool_name must not be empty`

**Example:**

```python
from aumai_toolemu import ToolMock, MockResponse, MockBehavior

# Conditional mock: different responses for different cities
mock = ToolMock(
    tool_name="weather",
    behavior=MockBehavior.conditional,
    conditions={"city": "London"},
    responses=[
        MockResponse(status_code=200, body={"temp": 8}),   # returned for London
        MockResponse(status_code=200, body={"temp": 25}),  # returned for everything else
    ],
)
```

---

### `EmulatorConfig`

```python
class EmulatorConfig(BaseModel):
    mocks: list[ToolMock] = []
    default_latency_ms: float = 0.0
    record_calls: bool = True
```

Top-level configuration for a `ToolEmulator` instance.

**Fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `mocks` | `list[ToolMock]` | `[]` | All tool mocks. Each `ToolMock.tool_name` is used as a dict key in the emulator. |
| `default_latency_ms` | `float` | `0.0` | Latency applied to any response with `latency_ms = 0`. Set globally once here instead of per-response. |
| `record_calls` | `bool` | `True` | When `True`, every call is appended to the internal `_recorded_calls` list for later inspection. |

**Loading from YAML:**

```python
import yaml
from aumai_toolemu import EmulatorConfig

with open("mocks.yaml") as f:
    data = yaml.safe_load(f)

config = EmulatorConfig.model_validate(data)
```

**Loading from JSON:**

```python
import json
from aumai_toolemu import EmulatorConfig

with open("mocks.json") as f:
    data = json.load(f)

config = EmulatorConfig.model_validate(data)
```

---

### `RecordedCall`

```python
class RecordedCall(BaseModel):
    tool_name: str
    input_data: dict[str, object]
    response: MockResponse
    timestamp: datetime
```

A single recorded tool invocation. Instances are created automatically when `record_calls` is `True`.

**Fields:**

| Field | Type | Description |
|---|---|---|
| `tool_name` | `str` | Name of the tool that was called. |
| `input_data` | `dict[str, object]` | The input payload supplied by the caller. |
| `response` | `MockResponse` | The response that was returned. |
| `timestamp` | `datetime` | UTC datetime of the call (timezone-aware, `tzinfo=timezone.utc`). |

**Example:**

```python
calls = emulator.get_recorded_calls()

# Serialize to JSON for logging
import json
from pydantic import TypeAdapter

ta = TypeAdapter(list[RecordedCall])
print(json.dumps(ta.dump_python(calls, mode="json"), indent=2))
```

---

## HTTP API Reference

When running `EmulatorServer`, the following HTTP endpoints are available.

### `POST /tools/{tool_name}`

Invoke a mocked tool.

**Path parameter:** `tool_name` — must match a registered mock.

**Request body:** Optional JSON object. Passed as `input_data` to `ToolEmulator.call()`.

**Response:** The mock's configured JSON body with the mock's configured status code and headers.

**Error responses:**
- `404 Not Found` — tool not registered in the emulator.

```bash
curl -s -X POST http://127.0.0.1:9000/tools/search \
  -H "Content-Type: application/json" \
  -d '{"query": "hello"}'
```

---

### `GET /calls`

Return all recorded calls as a JSON array.

**Response:** `200 OK` with an array of serialized `RecordedCall` objects.

```bash
curl -s http://127.0.0.1:9000/calls | python -m json.tool
```

---

### `DELETE /calls`

Clear all recorded calls and reset sequential cursors.

**Response:** `200 OK` with `{"status": "reset"}`.

```bash
curl -s -X DELETE http://127.0.0.1:9000/calls
```

---

### `GET /health`

Health check endpoint.

**Response:** `200 OK` with `{"status": "ok"}`.

```bash
curl -s http://127.0.0.1:9000/health
```
