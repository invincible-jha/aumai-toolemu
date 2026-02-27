"""Quickstart examples for aumai-toolemu.

Run this file directly to verify your installation and see the emulator in action:

    python examples/quickstart.py

Each demo function is self-contained and demonstrates a distinct feature.
No external services or API keys are required.
"""

from __future__ import annotations

from aumai_toolemu import (
    EmulatorConfig,
    MockBehavior,
    MockResponse,
    ToolEmulator,
    ToolMock,
    ToolNotFoundError,
)


# ---------------------------------------------------------------------------
# Demo 1: Static mock — always return the same response
# ---------------------------------------------------------------------------

def demo_static_mock() -> None:
    """Show the simplest possible usage: a static mock that always returns one response."""
    print("\n--- Demo 1: Static Mock ---")

    config = EmulatorConfig(
        mocks=[
            ToolMock(
                tool_name="get_user",
                behavior=MockBehavior.static,
                responses=[
                    MockResponse(
                        status_code=200,
                        body={"id": 42, "name": "Alice", "role": "admin"},
                    )
                ],
            )
        ],
        record_calls=True,
    )

    emulator = ToolEmulator(config)

    # Call the tool multiple times — always returns the same thing
    for i in range(3):
        response = emulator.call("get_user", {"user_id": i})
        print(f"  Call {i + 1}: status={response.status_code}, name={response.body['name']}")

    # Inspect the recorded call history
    calls = emulator.get_recorded_calls()
    print(f"  Recorded {len(calls)} calls")
    print(f"  First call input: {calls[0].input_data}")


# ---------------------------------------------------------------------------
# Demo 2: Sequential mock — cycle through responses in order
# ---------------------------------------------------------------------------

def demo_sequential_mock() -> None:
    """Show sequential behavior: responses cycle in order, modeling paginated APIs."""
    print("\n--- Demo 2: Sequential Mock (Pagination) ---")

    config = EmulatorConfig(
        mocks=[
            ToolMock(
                tool_name="list_items",
                behavior=MockBehavior.sequential,
                responses=[
                    MockResponse(status_code=200, body={"items": ["apple", "banana"], "has_more": True}),
                    MockResponse(status_code=200, body={"items": ["cherry", "date"], "has_more": True}),
                    MockResponse(status_code=200, body={"items": [], "has_more": False}),
                ],
            )
        ]
    )

    emulator = ToolEmulator(config)

    # Simulate an agent that pages through results until empty
    all_items: list[str] = []
    page = 0
    while True:
        response = emulator.call("list_items", {"page": page})
        items: list[str] = response.body.get("items", [])  # type: ignore[assignment]
        all_items.extend(items)
        print(f"  Page {page}: got {items}, has_more={response.body['has_more']}")
        if not response.body["has_more"]:
            break
        page += 1

    print(f"  All items collected: {all_items}")


# ---------------------------------------------------------------------------
# Demo 3: Conditional mock — different responses for different inputs
# ---------------------------------------------------------------------------

def demo_conditional_mock() -> None:
    """Show conditional behavior: return different responses based on input field values."""
    print("\n--- Demo 3: Conditional Mock (Input-Driven) ---")

    config = EmulatorConfig(
        mocks=[
            ToolMock(
                tool_name="get_price",
                behavior=MockBehavior.conditional,
                # This condition matches when input_data["symbol"] == "AAPL"
                conditions={"symbol": "AAPL"},
                responses=[
                    MockResponse(status_code=200, body={"symbol": "AAPL", "price": 195.50}),
                    MockResponse(status_code=200, body={"symbol": "UNKNOWN", "price": 0.0}),
                ],
            )
        ]
    )

    emulator = ToolEmulator(config)

    # Ask for AAPL — matches the condition, returns first response
    aapl = emulator.call("get_price", {"symbol": "AAPL"})
    print(f"  AAPL price: ${aapl.body['price']}")

    # Ask for something else — no match, falls back to last response
    other = emulator.call("get_price", {"symbol": "XYZ"})
    print(f"  XYZ price: ${other.body['price']}")


# ---------------------------------------------------------------------------
# Demo 4: Error injection — chaos testing
# ---------------------------------------------------------------------------

def demo_error_injection() -> None:
    """Show error_rate: simulate a flaky API that fails a percentage of calls."""
    print("\n--- Demo 4: Error Injection (Chaos Testing) ---")

    config = EmulatorConfig(
        mocks=[
            ToolMock(
                tool_name="flaky_service",
                behavior=MockBehavior.static,
                # 40 % of calls will return a 500 error
                error_rate=0.4,
                responses=[
                    MockResponse(status_code=200, body={"status": "ok"})
                ],
            )
        ],
        record_calls=True,
    )

    emulator = ToolEmulator(config)

    successes = 0
    failures = 0
    for _ in range(50):
        r = emulator.call("flaky_service", {})
        if r.status_code == 200:
            successes += 1
        else:
            failures += 1

    print(f"  50 calls: {successes} successes, {failures} failures")
    print("  (Expected roughly 30 failures due to 40 % error_rate)")


# ---------------------------------------------------------------------------
# Demo 5: ToolNotFoundError — unknown tool handling
# ---------------------------------------------------------------------------

def demo_tool_not_found() -> None:
    """Show ToolNotFoundError when calling an unregistered tool."""
    print("\n--- Demo 5: ToolNotFoundError ---")

    # Emulator with no mocks registered
    emulator = ToolEmulator(EmulatorConfig())

    try:
        emulator.call("nonexistent_tool", {"query": "anything"})
    except ToolNotFoundError as exc:
        print(f"  Caught ToolNotFoundError: {exc}")

    # Register the tool at runtime and retry
    emulator.add_mock(
        ToolMock(
            tool_name="nonexistent_tool",
            responses=[MockResponse(status_code=200, body={"found": True})],
        )
    )
    r = emulator.call("nonexistent_tool", {"query": "anything"})
    print(f"  After add_mock: status={r.status_code}, found={r.body['found']}")


# ---------------------------------------------------------------------------
# Main: run all demos
# ---------------------------------------------------------------------------

def main() -> None:
    """Run all quickstart demos in sequence."""
    print("=" * 60)
    print("aumai-toolemu quickstart demos")
    print("=" * 60)

    demo_static_mock()
    demo_sequential_mock()
    demo_conditional_mock()
    demo_error_injection()
    demo_tool_not_found()

    print("\n" + "=" * 60)
    print("All demos completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
