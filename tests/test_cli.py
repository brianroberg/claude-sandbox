"""Tests for the main CLI entry point."""

import subprocess
import sys

import pytest
from click.testing import CliRunner

from claude_sandbox.args import Args
from claude_sandbox.cli import main, run_sandbox


class TestRunSandbox:
    """Test the run_sandbox orchestration function."""

    def test_exits_if_pulseaudio_fails_to_start(self, mocker):
        """Exits with error if PulseAudio cannot start."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=False)
        mocker.patch("claude_sandbox.cli.start_pulseaudio", return_value=False)
        mock_print = mocker.patch("builtins.print")

        with pytest.raises(SystemExit) as exc_info:
            run_sandbox(Args())

        assert exc_info.value.code == 1
        mock_print.assert_any_call("ERROR: Could not start PulseAudio.", file=sys.stderr)

    def test_starts_pulseaudio_if_not_running(self, mocker):
        """Starts PulseAudio if not already running."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=False)
        mock_start = mocker.patch("claude_sandbox.cli.start_pulseaudio", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.get_macos_audio_devices", return_value=(None, None))
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp")
        mocker.patch("os.environ.get", return_value="test-key")
        mocker.patch("subprocess.run")

        run_sandbox(Args())

        mock_start.assert_called_once()

    def test_builds_image_if_not_exists(self, mocker):
        """Builds Docker image if it doesn't exist."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=False)
        mock_build = mocker.patch("claude_sandbox.cli.build_image", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.get_macos_audio_devices", return_value=(None, None))
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp")
        mocker.patch("os.environ.get", return_value="test-key")
        mocker.patch("subprocess.run")

        run_sandbox(Args())

        mock_build.assert_called_once()

    def test_exits_if_image_build_fails(self, mocker):
        """Exits with error if image build fails."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.build_image", return_value=False)
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp")
        mock_print = mocker.patch("builtins.print")

        with pytest.raises(SystemExit) as exc_info:
            run_sandbox(Args())

        assert exc_info.value.code == 1
        mock_print.assert_any_call("ERROR: Failed to build Docker image.", file=sys.stderr)

    def test_exits_if_container_already_exists(self, mocker):
        """Exits with error if container already exists."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=True)
        mock_print = mocker.patch("builtins.print")

        with pytest.raises(SystemExit) as exc_info:
            run_sandbox(Args(profile="work"))

        assert exc_info.value.code == 1
        assert any(
            "already exists" in str(call) for call in mock_print.call_args_list
        )

    def test_exits_if_github_requirements_not_met(self, mocker):
        """Exits with error if GitHub requirements not met."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.get_git_config", return_value={
            "user_name": None,
            "user_email": None,
        })
        mocker.patch("claude_sandbox.cli.validate_github_requirements", return_value=(
            False, ["Missing git config"]
        ))
        mock_print = mocker.patch("builtins.print")

        with pytest.raises(SystemExit) as exc_info:
            run_sandbox(Args(enable_github=True))

        assert exc_info.value.code == 1
        assert any(
            "github" in str(call).lower() or "git" in str(call).lower()
            for call in mock_print.call_args_list
        )

    def test_creates_volumes(self, mocker):
        """Creates Docker volumes for home and workspace."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mock_ensure = mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.get_macos_audio_devices", return_value=(None, None))
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp")
        mocker.patch("os.environ.get", return_value="test-key")
        mocker.patch("subprocess.run")

        run_sandbox(Args(profile="work"))

        # Should be called twice: once for home, once for workspace
        assert mock_ensure.call_count == 2
        calls = [str(c) for c in mock_ensure.call_args_list]
        assert any("claude-sandbox-work" in c for c in calls)
        assert any("workspace" in c for c in calls)

    def test_runs_docker_in_interactive_mode(self, mocker):
        """Runs docker with -it for interactive mode."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.get_macos_audio_devices", return_value=(None, None))
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp")
        mocker.patch("os.environ.get", return_value="test-key")
        mock_run = mocker.patch("subprocess.run")

        run_sandbox(Args())

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "docker"
        assert args[1] == "run"
        assert "-it" in args

    def test_runs_docker_in_detached_mode(self, mocker):
        """Runs docker with -d for detached mode."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.get_macos_audio_devices", return_value=(None, None))
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp")
        mocker.patch("os.environ.get", return_value="test-key")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        mocker.patch("builtins.print")

        run_sandbox(Args(detach_mode=True))

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "-d" in args
        assert "-it" not in args


class TestMain:
    """Test the main entry point."""

    def test_main_invokes_click_command(self, mocker):
        """Main is a click command that calls run_sandbox."""
        runner = CliRunner()
        mock_run = mocker.patch("claude_sandbox.cli.run_sandbox")

        result = runner.invoke(main, ["--github", "work"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args.profile == "work"
        assert args.enable_github is True
