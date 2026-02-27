"""Comprehensive CLI tests for aumai-toolemu."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from aumai_toolemu.cli import main, _load_config
from aumai_toolemu.models import EmulatorConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# main group tests
# ---------------------------------------------------------------------------


class TestMainGroup:
    def test_version_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "call" in result.output
        assert "init-config" in result.output


# ---------------------------------------------------------------------------
# call command tests
# ---------------------------------------------------------------------------


class TestCallCommand:
    def test_call_with_config_exits_zero(
        self, runner: CliRunner, yaml_config_file: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "ping", "--config", str(yaml_config_file)],
        )
        assert result.exit_code == 0

    def test_call_with_config_outputs_json(
        self, runner: CliRunner, yaml_config_file: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "ping", "--config", str(yaml_config_file)],
        )
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_call_output_has_status_code(
        self, runner: CliRunner, yaml_config_file: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "ping", "--config", str(yaml_config_file)],
        )
        data = json.loads(result.output)
        assert "status_code" in data

    def test_call_output_has_body(
        self, runner: CliRunner, yaml_config_file: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "ping", "--config", str(yaml_config_file)],
        )
        data = json.loads(result.output)
        assert "body" in data

    def test_call_json_config_file(
        self, runner: CliRunner, json_config_file: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "ping", "--config", str(json_config_file)],
        )
        assert result.exit_code == 0

    def test_call_adhoc_no_config(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "any_tool"],
        )
        assert result.exit_code == 0

    def test_call_adhoc_custom_status_code(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "any_tool", "--status-code", "201"],
        )
        data = json.loads(result.output)
        assert data["status_code"] == 201

    def test_call_adhoc_custom_response_body(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "any_tool", "--response-body", '{"key": "value"}'],
        )
        data = json.loads(result.output)
        assert data["body"] == {"key": "value"}

    def test_call_with_input_json(
        self, runner: CliRunner, yaml_config_file: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "ping", "--config", str(yaml_config_file), "--input", '{"query": "test"}'],
        )
        assert result.exit_code == 0

    def test_call_short_tool_flag(
        self, runner: CliRunner, yaml_config_file: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "-t", "ping", "-c", str(yaml_config_file)],
        )
        assert result.exit_code == 0

    def test_call_missing_config_file_exits_nonzero(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "ping", "--config", str(tmp_path / "nonexistent.yaml")],
        )
        assert result.exit_code != 0

    def test_call_unknown_tool_in_config_exits_one(
        self, runner: CliRunner, yaml_config_file: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "unknown_tool", "--config", str(yaml_config_file)],
        )
        assert result.exit_code == 1

    def test_call_invalid_input_json_exits_one(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "any_tool", "--input", "not-valid-json"],
        )
        assert result.exit_code == 1

    def test_call_invalid_response_body_json_exits_one(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "any_tool", "--response-body", "not-valid-json"],
        )
        assert result.exit_code == 1

    def test_call_output_has_headers(
        self, runner: CliRunner, yaml_config_file: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "ping", "--config", str(yaml_config_file)],
        )
        data = json.loads(result.output)
        assert "headers" in data

    def test_call_output_has_latency_ms(
        self, runner: CliRunner, yaml_config_file: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["call", "--tool", "ping", "--config", str(yaml_config_file)],
        )
        data = json.loads(result.output)
        assert "latency_ms" in data

    def test_call_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["call", "--help"])
        assert result.exit_code == 0
        assert "--tool" in result.output

    def test_call_adhoc_response_body_200_status(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["call", "-t", "my_tool"])
        data = json.loads(result.output)
        assert data["status_code"] == 200


# ---------------------------------------------------------------------------
# init-config command tests
# ---------------------------------------------------------------------------


class TestInitConfigCommand:
    def test_init_config_creates_default_file(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init-config"])
            assert result.exit_code == 0
            assert Path("mocks.yaml").exists()

    def test_init_config_custom_output(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init-config", "--output", "custom.yaml"])
            assert result.exit_code == 0
            assert Path("custom.yaml").exists()

    def test_init_config_short_output_flag(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init-config", "-o", "out.yaml"])
            assert result.exit_code == 0
            assert Path("out.yaml").exists()

    def test_init_config_file_is_valid_yaml(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["init-config"])
            content = Path("mocks.yaml").read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            assert isinstance(data, dict)

    def test_init_config_file_is_valid_emulator_config(
        self, runner: CliRunner
    ) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["init-config"])
            content = Path("mocks.yaml").read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            config = EmulatorConfig.model_validate(data)
            assert len(config.mocks) > 0

    def test_init_config_contains_search_mock(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["init-config"])
            content = Path("mocks.yaml").read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            tool_names = [m["tool_name"] for m in data.get("mocks", [])]
            assert "search" in tool_names

    def test_init_config_existing_file_without_force_fails(
        self, runner: CliRunner
    ) -> None:
        with runner.isolated_filesystem():
            Path("mocks.yaml").write_text("old content", encoding="utf-8")
            result = runner.invoke(main, ["init-config"])
            assert result.exit_code == 1

    def test_init_config_force_overwrites(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            Path("mocks.yaml").write_text("old content", encoding="utf-8")
            result = runner.invoke(main, ["init-config", "--force"])
            assert result.exit_code == 0
            content = Path("mocks.yaml").read_text(encoding="utf-8")
            assert "old content" not in content

    def test_init_config_success_message(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init-config"])
            assert "Created" in result.output

    def test_init_config_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["init-config", "--help"])
        assert result.exit_code == 0
        assert "output" in result.output or "output" in result.output.lower()


# ---------------------------------------------------------------------------
# _load_config helper tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_load_yaml_config(self, yaml_config_file: Path) -> None:
        config = _load_config(str(yaml_config_file))
        assert isinstance(config, EmulatorConfig)

    def test_load_json_config(self, json_config_file: Path) -> None:
        config = _load_config(str(json_config_file))
        assert isinstance(config, EmulatorConfig)

    def test_load_yaml_has_ping_mock(self, yaml_config_file: Path) -> None:
        config = _load_config(str(yaml_config_file))
        tool_names = [m.tool_name for m in config.mocks]
        assert "ping" in tool_names

    def test_load_json_has_ping_mock(self, json_config_file: Path) -> None:
        config = _load_config(str(json_config_file))
        tool_names = [m.tool_name for m in config.mocks]
        assert "ping" in tool_names

    def test_load_nonexistent_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(Exception):
            _load_config(str(tmp_path / "nonexistent.yaml"))

    def test_load_invalid_json_raises(self, tmp_path: Path) -> None:
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not valid json", encoding="utf-8")
        with pytest.raises(Exception):
            _load_config(str(bad_json))
