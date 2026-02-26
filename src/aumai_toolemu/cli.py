"""CLI entry point for aumai-toolemu."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml

from aumai_toolemu.models import (
    EmulatorConfig,
    MockBehavior,
    MockResponse,
    ToolMock,
)


def _load_config(config_path: str) -> EmulatorConfig:
    """Load an EmulatorConfig from a YAML or JSON file."""
    path = Path(config_path)
    raw_text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(raw_text)
    else:
        data = json.loads(raw_text)
    return EmulatorConfig.model_validate(data)


@click.group()
@click.version_option()
def main() -> None:
    """AumAI ToolEmu CLI — emulate tool calls for agent testing."""


@main.command("serve")
@click.option(
    "--config",
    "-c",
    "config_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to the emulator config file (YAML or JSON).",
)
@click.option(
    "--port",
    "-p",
    default=9000,
    show_default=True,
    type=int,
    help="Port to bind the server to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host address to bind.",
)
def serve_command(config_path: str, port: int, host: str) -> None:
    """Start the tool emulator HTTP server."""
    try:
        config = _load_config(config_path)
    except Exception as exc:
        click.echo(f"Failed to load config: {exc}", err=True)
        sys.exit(1)

    from aumai_toolemu.core import EmulatorServer

    click.echo(f"Starting AumAI Tool Emulator on {host}:{port}")
    click.echo(f"Registered mocks: {[m.tool_name for m in config.mocks]}")
    server = EmulatorServer(config)
    server.run(host=host, port=port)


@main.command("call")
@click.option(
    "--tool",
    "-t",
    "tool_name",
    required=True,
    help="Name of the tool to emulate.",
)
@click.option(
    "--input",
    "-i",
    "input_json",
    default="{}",
    help="JSON string with input data.",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to a config file to load mocks from.",
)
@click.option(
    "--status-code",
    default=200,
    type=int,
    help="Response status code for ad-hoc calls (no config).",
)
@click.option(
    "--response-body",
    default=None,
    help="JSON string for ad-hoc response body.",
)
def call_command(
    tool_name: str,
    input_json: str,
    config_path: str | None,
    status_code: int,
    response_body: str | None,
) -> None:
    """Invoke an emulated tool and print the response.

    When --config is provided the registered mock is used.
    When no config is given, an ad-hoc static mock is created.
    """
    from aumai_toolemu.core import ToolEmulator, ToolNotFoundError

    try:
        input_data: dict[str, object] = json.loads(input_json)
    except json.JSONDecodeError as exc:
        click.echo(f"Invalid JSON for --input: {exc}", err=True)
        sys.exit(1)

    if config_path:
        try:
            config = _load_config(config_path)
        except Exception as exc:
            click.echo(f"Failed to load config: {exc}", err=True)
            sys.exit(1)
    else:
        body: dict[str, object] = {}
        if response_body:
            try:
                body = json.loads(response_body)
            except json.JSONDecodeError as exc:
                click.echo(f"Invalid JSON for --response-body: {exc}", err=True)
                sys.exit(1)
        config = EmulatorConfig(
            mocks=[
                ToolMock(
                    tool_name=tool_name,
                    behavior=MockBehavior.static,
                    responses=[MockResponse(status_code=status_code, body=body)],
                )
            ]
        )

    emulator = ToolEmulator(config)
    try:
        response = emulator.call(tool_name, input_data)
    except ToolNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    output = {
        "status_code": response.status_code,
        "body": response.body,
        "headers": response.headers,
        "latency_ms": response.latency_ms,
    }
    click.echo(json.dumps(output, indent=2))


@main.command("init-config")
@click.option(
    "--output",
    "-o",
    default="mocks.yaml",
    show_default=True,
    help="Destination config file.",
)
@click.option("--force", is_flag=True, default=False, help="Overwrite if exists.")
def init_config_command(output: str, force: bool) -> None:
    """Generate an example emulator config file."""
    destination = Path(output)
    if destination.exists() and not force:
        click.echo(f"File already exists: {output}. Use --force to overwrite.", err=True)
        sys.exit(1)

    example: dict[str, object] = {
        "default_latency_ms": 50.0,
        "record_calls": True,
        "mocks": [
            {
                "tool_name": "search",
                "behavior": "sequential",
                "error_rate": 0.0,
                "responses": [
                    {
                        "status_code": 200,
                        "latency_ms": 50.0,
                        "body": {"results": ["result_1", "result_2"]},
                        "headers": {"content-type": "application/json"},
                    },
                    {
                        "status_code": 200,
                        "latency_ms": 80.0,
                        "body": {"results": []},
                        "headers": {"content-type": "application/json"},
                    },
                ],
            },
            {
                "tool_name": "calculator",
                "behavior": "static",
                "error_rate": 0.1,
                "responses": [
                    {
                        "status_code": 200,
                        "latency_ms": 10.0,
                        "body": {"result": 42},
                        "headers": {},
                    }
                ],
            },
        ],
    }
    content = yaml.dump(example, default_flow_style=False, sort_keys=False, allow_unicode=True)
    destination.write_text(content, encoding="utf-8")
    click.echo(f"Created {output}")


if __name__ == "__main__":
    main()
