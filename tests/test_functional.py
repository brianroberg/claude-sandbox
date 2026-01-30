"""Functional tests for claude-sandbox end-to-end behavior."""

import subprocess

import pytest
from click.testing import CliRunner

from claude_sandbox.args import Args
from claude_sandbox.cli import main, run_sandbox


class TestClickCli:
    """Test click CLI argument parsing."""

    @pytest.fixture
    def runner(self):
        """Create a Click CLI test runner."""
        return CliRunner()

    def test_no_args_uses_defaults(self, runner, mocker):
        """With no arguments, uses default profile."""
        mocker.patch("claude_sandbox.cli.run_sandbox")
        result = runner.invoke(main, [])
        assert result.exit_code == 0

    def test_profile_argument(self, runner, mocker):
        """Profile can be specified as positional argument."""
        mock_run = mocker.patch("claude_sandbox.cli.run_sandbox")
        result = runner.invoke(main, ["work"])
        assert result.exit_code == 0
        args = mock_run.call_args[0][0]
        assert args.profile == "work"

    def test_github_flag(self, runner, mocker):
        """--github flag enables GitHub access."""
        mock_run = mocker.patch("claude_sandbox.cli.run_sandbox")
        result = runner.invoke(main, ["--github"])
        assert result.exit_code == 0
        args = mock_run.call_args[0][0]
        assert args.enable_github is True

    def test_detach_long_flag(self, runner, mocker):
        """--detach flag enables detached mode."""
        mock_run = mocker.patch("claude_sandbox.cli.run_sandbox")
        result = runner.invoke(main, ["--detach"])
        assert result.exit_code == 0
        args = mock_run.call_args[0][0]
        assert args.detach_mode is True

    def test_detach_short_flag(self, runner, mocker):
        """-d flag enables detached mode."""
        mock_run = mocker.patch("claude_sandbox.cli.run_sandbox")
        result = runner.invoke(main, ["-d"])
        assert result.exit_code == 0
        args = mock_run.call_args[0][0]
        assert args.detach_mode is True

    def test_single_host_port(self, runner, mocker):
        """--host-port adds a port to the list."""
        mock_run = mocker.patch("claude_sandbox.cli.run_sandbox")
        result = runner.invoke(main, ["--host-port", "8080"])
        assert result.exit_code == 0
        args = mock_run.call_args[0][0]
        assert args.host_ports == [8080]

    def test_multiple_host_ports(self, runner, mocker):
        """Multiple --host-port flags accumulate."""
        mock_run = mocker.patch("claude_sandbox.cli.run_sandbox")
        result = runner.invoke(main, ["--host-port", "8080", "--host-port", "3000"])
        assert result.exit_code == 0
        args = mock_run.call_args[0][0]
        assert args.host_ports == [8080, 3000]

    def test_host_port_invalid_value_fails(self, runner, mocker):
        """--host-port with non-numeric value fails."""
        mocker.patch("claude_sandbox.cli.run_sandbox")
        result = runner.invoke(main, ["--host-port", "abc"])
        assert result.exit_code != 0

    def test_host_port_out_of_range_fails(self, runner, mocker):
        """--host-port with port outside 1-65535 fails."""
        mocker.patch("claude_sandbox.cli.run_sandbox")

        result = runner.invoke(main, ["--host-port", "0"])
        assert result.exit_code != 0

        result = runner.invoke(main, ["--host-port", "65536"])
        assert result.exit_code != 0

    def test_all_options_combined(self, runner, mocker):
        """All options work together correctly."""
        mock_run = mocker.patch("claude_sandbox.cli.run_sandbox")
        result = runner.invoke(main, [
            "--github",
            "-d",
            "--host-port", "8080",
            "--host-port", "3000",
            "myproject",
        ])
        assert result.exit_code == 0
        args = mock_run.call_args[0][0]
        assert args.profile == "myproject"
        assert args.enable_github is True
        assert args.detach_mode is True
        assert args.host_ports == [8080, 3000]

    def test_help_option(self, runner):
        """--help shows usage information."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Launch Claude Code" in result.output
        assert "--github" in result.output
        assert "--detach" in result.output
        assert "--host-port" in result.output

    def test_help_short_option(self, runner):
        """-h shows usage information."""
        result = runner.invoke(main, ["-h"])
        assert result.exit_code == 0
        assert "Launch Claude Code" in result.output


class TestFunctionalBasicFlow:
    """Test basic sandbox launch flow."""

    @pytest.fixture
    def mock_all_externals(self, mocker):
        """Mock all external system calls for functional tests."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.get_macos_audio_devices", return_value=(None, None))
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp/test")
        mocker.patch("os.environ.get", side_effect=lambda k, d="": {
            "ANTHROPIC_API_KEY": "test-api-key",
            "TERM": "xterm-256color",
        }.get(k, d))
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        return mock_run

    def test_default_profile_launches_correctly(self, mock_all_externals, capsys):
        """Default profile launches with expected Docker arguments."""
        args = Args()
        run_sandbox(args)

        mock_all_externals.assert_called_once()
        cmd = mock_all_externals.call_args[0][0]

        # Verify it's a docker run command
        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        assert "-it" in cmd

        # Verify default profile names
        assert any("claude-sandbox-default:/home/claude" in arg for arg in cmd)
        assert any("claude-sandbox-default-workspace:/workspace" in arg for arg in cmd)

        # Verify image name and /bin/bash at end
        assert "claude-sandbox" in cmd
        assert cmd[-1] == "/bin/bash"

    def test_custom_profile_uses_profile_name(self, mock_all_externals, mocker):
        """Custom profile name is used in volume and container names."""
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)

        args = Args(profile="myproject")
        run_sandbox(args)

        cmd = mock_all_externals.call_args[0][0]
        assert any("claude-sandbox-myproject:/home/claude" in arg for arg in cmd)
        assert any("claude-sandbox-myproject-workspace:/workspace" in arg for arg in cmd)
        assert any(arg == "claude-sandbox-myproject" for arg in cmd)  # hostname/name


class TestFunctionalWithGitHub:
    """Test GitHub-enabled flow."""

    @pytest.fixture
    def mock_github_externals(self, mocker):
        """Mock externals with GitHub enabled."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.get_macos_audio_devices", return_value=(None, None))
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp/test")
        mocker.patch("claude_sandbox.cli.get_git_config", return_value={
            "user_name": "Test User",
            "user_email": "test@example.com",
        })
        mocker.patch("claude_sandbox.cli.validate_github_requirements", return_value=(True, []))
        mocker.patch("os.environ.get", side_effect=lambda k, d="": {
            "ANTHROPIC_API_KEY": "test-api-key",
            "TERM": "xterm-256color",
            "SSH_AUTH_SOCK": "/tmp/ssh.sock",
        }.get(k, d))
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        return mock_run

    def test_github_flag_adds_ssh_and_git_config(self, mock_github_externals):
        """--github flag adds SSH socket and git config to Docker args."""
        args = Args(enable_github=True)
        run_sandbox(args)

        cmd = mock_github_externals.call_args[0][0]

        # Check SSH socket mount
        assert any("ssh-auth.sock" in arg for arg in cmd)

        # Check git environment variables
        assert any("GIT_AUTHOR_NAME=Test User" in arg for arg in cmd)
        assert any("GIT_AUTHOR_EMAIL=test@example.com" in arg for arg in cmd)
        assert any("GIT_COMMITTER_NAME=Test User" in arg for arg in cmd)
        assert any("GIT_COMMITTER_EMAIL=test@example.com" in arg for arg in cmd)


class TestFunctionalDetachedMode:
    """Test detached mode flow."""

    @pytest.fixture
    def mock_detach_externals(self, mocker):
        """Mock externals for detached mode."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.get_macos_audio_devices", return_value=(None, None))
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp/test")
        mocker.patch("os.environ.get", side_effect=lambda k, d="": {
            "ANTHROPIC_API_KEY": "test-api-key",
            "TERM": "xterm-256color",
        }.get(k, d))
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        mocker.patch("builtins.print")
        return mock_run

    def test_detach_mode_uses_d_flag(self, mock_detach_externals):
        """Detached mode uses -d flag instead of -it."""
        args = Args(detach_mode=True)
        run_sandbox(args)

        cmd = mock_detach_externals.call_args[0][0]
        assert "-d" in cmd
        assert "-it" not in cmd

    def test_detach_mode_runs_sleep_infinity(self, mock_detach_externals):
        """Detached mode runs 'sleep infinity' as command."""
        args = Args(detach_mode=True)
        run_sandbox(args)

        cmd = mock_detach_externals.call_args[0][0]
        assert "sleep" in cmd
        assert "infinity" in cmd


class TestFunctionalHostPorts:
    """Test host port access flow."""

    @pytest.fixture
    def mock_port_externals(self, mocker):
        """Mock externals for port testing."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.get_macos_audio_devices", return_value=(None, None))
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp/test")
        mocker.patch("os.environ.get", side_effect=lambda k, d="": {
            "ANTHROPIC_API_KEY": "test-api-key",
            "TERM": "xterm-256color",
        }.get(k, d))
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        return mock_run

    def test_host_ports_passed_to_container(self, mock_port_externals):
        """Host ports are passed as environment variable."""
        args = Args(host_ports=[8080, 3000])
        run_sandbox(args)

        cmd = mock_port_externals.call_args[0][0]
        # Find HOST_PORTS env var
        host_ports_found = False
        for i, arg in enumerate(cmd):
            if arg == "-e" and i + 1 < len(cmd) and cmd[i + 1].startswith("HOST_PORTS="):
                host_ports_found = True
                assert "8080" in cmd[i + 1]
                assert "3000" in cmd[i + 1]
                break
        assert host_ports_found


class TestFunctionalErrorCases:
    """Test error handling in functional scenarios."""

    def test_exits_on_pulseaudio_failure(self, mocker):
        """Exits with code 1 when PulseAudio fails."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=False)
        mocker.patch("claude_sandbox.cli.start_pulseaudio", return_value=False)
        mocker.patch("builtins.print")

        with pytest.raises(SystemExit) as exc_info:
            run_sandbox(Args())

        assert exc_info.value.code == 1

    def test_exits_on_container_conflict(self, mocker):
        """Exits with code 1 when container already exists."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=True)
        mocker.patch("builtins.print")

        with pytest.raises(SystemExit) as exc_info:
            run_sandbox(Args())

        assert exc_info.value.code == 1


class TestFunctionalCombinedOptions:
    """Test combinations of options."""

    @pytest.fixture
    def mock_combined_externals(self, mocker):
        """Mock externals for combined option testing."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=False)
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.get_macos_audio_devices", return_value=(None, None))
        mocker.patch("claude_sandbox.cli.get_script_dir", return_value="/tmp/test")
        mocker.patch("claude_sandbox.cli.get_git_config", return_value={
            "user_name": "Test User",
            "user_email": "test@example.com",
        })
        mocker.patch("claude_sandbox.cli.validate_github_requirements", return_value=(True, []))
        mocker.patch("os.environ.get", side_effect=lambda k, d="": {
            "ANTHROPIC_API_KEY": "test-api-key",
            "TERM": "xterm-256color",
            "SSH_AUTH_SOCK": "/tmp/ssh.sock",
        }.get(k, d))
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        mocker.patch("builtins.print")
        return mock_run

    def test_all_options_combined(self, mock_combined_externals):
        """All options work together correctly."""
        args = Args(
            profile="myproject",
            enable_github=True,
            detach_mode=True,
            host_ports=[8080, 3000],
        )
        run_sandbox(args)

        cmd = mock_combined_externals.call_args[0][0]

        # Detached mode
        assert "-d" in cmd
        assert "-it" not in cmd

        # GitHub
        assert any("GIT_AUTHOR_NAME=Test User" in arg for arg in cmd)

        # Profile
        assert any("claude-sandbox-myproject:/home/claude" in arg for arg in cmd)

        # Host ports
        assert any("HOST_PORTS=" in arg and "8080" in arg for arg in cmd)

        # Sleep infinity for detached
        assert "sleep" in cmd
        assert "infinity" in cmd
