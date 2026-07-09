import pytest
from click.testing import CliRunner
from harness.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "status" in result.output
    assert "report" in result.output
    assert "list" in result.output
    assert "cancel" in result.output
    assert "config" in result.output


def test_run_missing_task_file(runner):
    result = runner.invoke(cli, ["run", "nonexistent.yaml"])
    assert result.exit_code != 0


def test_status_no_args(runner, temp_dir):
    result = runner.invoke(cli, ["status", "--data-dir", str(temp_dir)])
    assert result.exit_code == 0


def test_list_no_args(runner, temp_dir):
    result = runner.invoke(cli, ["list", "--data-dir", str(temp_dir)])
    assert result.exit_code == 0


def test_config(runner):
    result = runner.invoke(cli, ["config"])
    assert result.exit_code == 0
    assert "model" in result.output.lower() or "gpt" in result.output.lower() or "config" in result.output.lower()