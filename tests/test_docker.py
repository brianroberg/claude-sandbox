"""Tests for Docker operations."""

import subprocess

from claude_sandbox.docker import (
    build_docker_args,
    build_image,
    check_container_exists,
    check_image_exists,
    ensure_volume_exists,
)


class TestEnsureVolumeExists:
    """Test Docker volume management."""

    def test_creates_volume_if_not_exists(self, mocker):
        """Creates volume when it doesn't exist."""
        mock_run = mocker.patch("subprocess.run")
        # First call (inspect) fails, second call (create) succeeds
        mock_run.side_effect = [
            subprocess.CompletedProcess([], 1),  # inspect fails
            subprocess.CompletedProcess([], 0),  # create succeeds
        ]

        result = ensure_volume_exists("test-volume")

        assert result is True
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["docker", "volume", "inspect", "test-volume"],
            capture_output=True,
            check=False,
        )
        mock_run.assert_any_call(
            ["docker", "volume", "create", "test-volume"],
            capture_output=True,
            check=False,
        )

    def test_skips_creation_if_exists(self, mocker):
        """Skips creation when volume already exists."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)

        result = ensure_volume_exists("test-volume")

        assert result is True
        mock_run.assert_called_once_with(
            ["docker", "volume", "inspect", "test-volume"],
            capture_output=True,
            check=False,
        )

    def test_returns_false_on_create_failure(self, mocker):
        """Returns False when volume creation fails."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            subprocess.CompletedProcess([], 1),  # inspect fails
            subprocess.CompletedProcess([], 1),  # create fails
        ]

        result = ensure_volume_exists("test-volume")

        assert result is False


class TestCheckImageExists:
    """Test Docker image existence checks."""

    def test_returns_true_when_image_exists(self, mocker):
        """Returns True when image exists."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)

        result = check_image_exists("claude-sandbox")

        assert result is True
        mock_run.assert_called_once_with(
            ["docker", "image", "inspect", "claude-sandbox"],
            capture_output=True,
            check=False,
        )

    def test_returns_false_when_image_missing(self, mocker):
        """Returns False when image doesn't exist."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 1)

        result = check_image_exists("claude-sandbox")

        assert result is False


class TestBuildImage:
    """Test Docker image building."""

    def test_builds_image_successfully(self, mocker):
        """Builds image and returns True on success."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)

        result = build_image("claude-sandbox", "/path/to/context")

        assert result is True
        mock_run.assert_called_once_with(
            ["docker", "build", "-t", "claude-sandbox", "/path/to/context"],
            check=False,
        )

    def test_returns_false_on_build_failure(self, mocker):
        """Returns False when build fails."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 1)

        result = build_image("claude-sandbox", "/path/to/context")

        assert result is False


class TestCheckContainerExists:
    """Test container existence checks."""

    def test_returns_true_when_container_exists(self, mocker):
        """Returns True when container exists."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout=b"claude-sandbox-work\n"
        )

        result = check_container_exists("claude-sandbox-work")

        assert result is True

    def test_returns_false_when_container_missing(self, mocker):
        """Returns False when container doesn't exist."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout=b"other-container\n"
        )

        result = check_container_exists("claude-sandbox-work")

        assert result is False

    def test_returns_false_on_empty_output(self, mocker):
        """Returns False when no containers exist."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout=b"")

        result = check_container_exists("claude-sandbox-work")

        assert result is False


class TestBuildDockerArgs:
    """Test Docker run command argument building."""

    def test_basic_args(self):
        """Builds basic docker args without optional features."""
        args = build_docker_args(
            container_name="claude-sandbox-default",
            volume_name="claude-sandbox-default",
            workspace_volume_name="claude-sandbox-default-workspace",
            host_ports=[],
            enable_github=False,
            github_config=None,
            api_key="test-key",
            term="xterm-256color",
        )

        assert "--rm" in args
        assert "--cap-add=NET_ADMIN" in args
        assert "--add-host=host.docker.internal:host-gateway" in args
        assert "-v" in args
        assert "claude-sandbox-default:/home/claude" in args
        assert "claude-sandbox-default-workspace:/workspace" in args
        assert "-e" in args
        assert "ANTHROPIC_API_KEY=test-key" in args
        assert "TERM=xterm-256color" in args
        assert "--hostname" in args
        assert "--name" in args

    def test_with_host_ports(self):
        """Includes HOST_PORTS env var when ports specified."""
        args = build_docker_args(
            container_name="claude-sandbox-default",
            volume_name="claude-sandbox-default",
            workspace_volume_name="claude-sandbox-default-workspace",
            host_ports=[8080, 3000],
            enable_github=False,
            github_config=None,
            api_key="",
            term="xterm",
        )

        # Find the HOST_PORTS environment variable
        host_ports_found = False
        for i, arg in enumerate(args):
            if arg == "-e" and i + 1 < len(args) and args[i + 1].startswith("HOST_PORTS="):
                host_ports_found = True
                assert args[i + 1] == "HOST_PORTS=8080 3000"
                break
        assert host_ports_found

    def test_with_github_enabled(self):
        """Includes GitHub-related args when enabled."""
        github_config = {
            "user_name": "Test User",
            "user_email": "test@example.com",
        }

        args = build_docker_args(
            container_name="claude-sandbox-default",
            volume_name="claude-sandbox-default",
            workspace_volume_name="claude-sandbox-default-workspace",
            host_ports=[],
            enable_github=True,
            github_config=github_config,
            api_key="",
            term="xterm",
        )

        # Check for SSH socket mount
        ssh_mount_found = False
        for i, arg in enumerate(args):
            if arg == "-v" and i + 1 < len(args) and "ssh-auth.sock" in args[i + 1]:
                ssh_mount_found = True
                break
        assert ssh_mount_found

        # Check for SSH_AUTH_SOCK env var
        ssh_env_found = False
        for i, arg in enumerate(args):
            if arg == "-e" and i + 1 < len(args) and args[i + 1].startswith("SSH_AUTH_SOCK="):
                ssh_env_found = True
                break
        assert ssh_env_found

        # Check for git author/committer env vars
        assert any("GIT_AUTHOR_NAME=Test User" in arg for arg in args)
        assert any("GIT_AUTHOR_EMAIL=test@example.com" in arg for arg in args)
        assert any("GIT_COMMITTER_NAME=Test User" in arg for arg in args)
        assert any("GIT_COMMITTER_EMAIL=test@example.com" in arg for arg in args)

    def test_pulse_server_configured(self):
        """Includes PulseAudio server configuration."""
        args = build_docker_args(
            container_name="test",
            volume_name="test",
            workspace_volume_name="test-workspace",
            host_ports=[],
            enable_github=False,
            github_config=None,
            api_key="",
            term="xterm",
        )

        pulse_found = False
        for i, arg in enumerate(args):
            if arg == "-e" and i + 1 < len(args) and "PULSE_SERVER=" in args[i + 1]:
                pulse_found = True
                assert "tcp:host.docker.internal:4713" in args[i + 1]
                break
        assert pulse_found
