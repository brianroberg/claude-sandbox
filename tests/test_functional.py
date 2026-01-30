"""Functional tests for claude-sandbox end-to-end behavior."""

import subprocess

import pytest

from claude_sandbox.cli import run_sandbox


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
        run_sandbox([])

        mock_all_externals.assert_called_once()
        args = mock_all_externals.call_args[0][0]

        # Verify it's a docker run command
        assert args[0] == "docker"
        assert args[1] == "run"
        assert "-it" in args

        # Verify default profile names
        assert any("claude-sandbox-default:/home/claude" in arg for arg in args)
        assert any("claude-sandbox-default-workspace:/workspace" in arg for arg in args)

        # Verify image name at end
        assert "claude-sandbox" in args

    def test_custom_profile_uses_profile_name(self, mock_all_externals, mocker):
        """Custom profile name is used in volume and container names."""
        mocker.patch("claude_sandbox.cli.ensure_volume_exists", return_value=True)

        run_sandbox(["myproject"])

        args = mock_all_externals.call_args[0][0]
        assert any("claude-sandbox-myproject:/home/claude" in arg for arg in args)
        assert any("claude-sandbox-myproject-workspace:/workspace" in arg for arg in args)
        assert any(arg == "claude-sandbox-myproject" for arg in args)  # hostname/name

    def test_command_passthrough(self, mock_all_externals):
        """Command after -- is passed to Docker."""
        run_sandbox(["--", "/bin/bash", "-c", "echo hello"])

        args = mock_all_externals.call_args[0][0]
        # Find claude-sandbox image in args, command comes after
        image_idx = None
        for i, arg in enumerate(args):
            if arg == "claude-sandbox" and i > 5:  # Skip early args
                image_idx = i
                break

        assert image_idx is not None
        remaining = args[image_idx + 1:]
        assert "/bin/bash" in remaining
        assert "-c" in remaining
        assert "echo hello" in remaining


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
        run_sandbox(["--github"])

        args = mock_github_externals.call_args[0][0]

        # Check SSH socket mount
        assert any("ssh-auth.sock" in arg for arg in args)

        # Check git environment variables
        assert any("GIT_AUTHOR_NAME=Test User" in arg for arg in args)
        assert any("GIT_AUTHOR_EMAIL=test@example.com" in arg for arg in args)
        assert any("GIT_COMMITTER_NAME=Test User" in arg for arg in args)
        assert any("GIT_COMMITTER_EMAIL=test@example.com" in arg for arg in args)


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
        run_sandbox(["--detach"])

        args = mock_detach_externals.call_args[0][0]
        assert "-d" in args
        assert "-it" not in args

    def test_detach_mode_runs_sleep_infinity(self, mock_detach_externals):
        """Detached mode runs 'sleep infinity' as command."""
        run_sandbox(["-d"])

        args = mock_detach_externals.call_args[0][0]
        assert "sleep" in args
        assert "infinity" in args


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
        run_sandbox(["--host-port", "8080", "--host-port", "3000"])

        args = mock_port_externals.call_args[0][0]
        # Find HOST_PORTS env var
        host_ports_found = False
        for i, arg in enumerate(args):
            if arg == "-e" and i + 1 < len(args) and args[i + 1].startswith("HOST_PORTS="):
                host_ports_found = True
                assert "8080" in args[i + 1]
                assert "3000" in args[i + 1]
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
            run_sandbox([])

        assert exc_info.value.code == 1

    def test_exits_on_container_conflict(self, mocker):
        """Exits with code 1 when container already exists."""
        mocker.patch("claude_sandbox.cli.check_pulseaudio_running", return_value=True)
        mocker.patch("claude_sandbox.cli.check_image_exists", return_value=True)
        mocker.patch("claude_sandbox.cli.check_container_exists", return_value=True)
        mocker.patch("builtins.print")

        with pytest.raises(SystemExit) as exc_info:
            run_sandbox([])

        assert exc_info.value.code == 1

    def test_exits_on_invalid_port(self, mocker, capsys):
        """Exits with code when port is invalid."""
        with pytest.raises(SystemExit):
            run_sandbox(["--host-port", "invalid"])

    def test_exits_on_port_out_of_range(self, mocker, capsys):
        """Exits when port is out of range."""
        with pytest.raises(SystemExit):
            run_sandbox(["--host-port", "70000"])


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
        run_sandbox([
            "--github",
            "-d",
            "--host-port", "8080",
            "--host-port", "3000",
            "myproject",
        ])

        args = mock_combined_externals.call_args[0][0]

        # Detached mode
        assert "-d" in args
        assert "-it" not in args

        # GitHub
        assert any("GIT_AUTHOR_NAME=Test User" in arg for arg in args)

        # Profile
        assert any("claude-sandbox-myproject:/home/claude" in arg for arg in args)

        # Host ports
        assert any("HOST_PORTS=" in arg and "8080" in arg for arg in args)

        # Sleep infinity for detached
        assert "sleep" in args
        assert "infinity" in args
