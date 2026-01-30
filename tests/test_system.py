"""Tests for system operations (audio, GitHub setup)."""

import os
import subprocess

from claude_sandbox.system import (
    check_pulseaudio_running,
    get_git_config,
    get_macos_audio_devices,
    start_pulseaudio,
    sync_pulseaudio_defaults,
    validate_github_requirements,
)


class TestCheckPulseaudioRunning:
    """Test PulseAudio status checks."""

    def test_returns_true_when_running(self, mocker):
        """Returns True when PulseAudio is running."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)

        result = check_pulseaudio_running()

        assert result is True
        mock_run.assert_called_once_with(
            ["pulseaudio", "--check"],
            capture_output=True,
            check=False,
        )

    def test_returns_false_when_not_running(self, mocker):
        """Returns False when PulseAudio is not running."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 1)

        result = check_pulseaudio_running()

        assert result is False


class TestStartPulseaudio:
    """Test PulseAudio startup."""

    def test_starts_successfully(self, mocker):
        """Returns True when PulseAudio starts successfully."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0)

        result = start_pulseaudio()

        assert result is True
        mock_run.assert_called_once_with(
            ["pulseaudio", "--exit-idle-time=-1", "--daemon"],
            capture_output=True,
            check=False,
        )

    def test_returns_false_on_failure(self, mocker):
        """Returns False when PulseAudio fails to start."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 1)

        result = start_pulseaudio()

        assert result is False


class TestGetMacosAudioDevices:
    """Test macOS audio device detection."""

    def test_returns_devices_when_available(self, mocker):
        """Returns output and input device names."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout=b"MacBook Pro Speakers\n"),
            subprocess.CompletedProcess([], 0, stdout=b"MacBook Pro Microphone\n"),
        ]

        output, input_dev = get_macos_audio_devices()

        assert output == "MacBook Pro Speakers"
        assert input_dev == "MacBook Pro Microphone"

    def test_returns_none_when_command_not_found(self, mocker):
        """Returns None when SwitchAudioSource is not available."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = FileNotFoundError()

        output, input_dev = get_macos_audio_devices()

        assert output is None
        assert input_dev is None

    def test_returns_none_on_command_failure(self, mocker):
        """Returns None when command fails."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 1, stdout=b"")

        output, input_dev = get_macos_audio_devices()

        assert output is None
        assert input_dev is None


class TestSyncPulseaudioDefaults:
    """Test PulseAudio default device sync."""

    def test_sets_defaults_when_devices_found(self, mocker):
        """Sets PulseAudio defaults when matching devices found."""
        mock_run = mocker.patch("subprocess.run")
        # pactl list sinks output
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                [], 0,
                stdout=b"Name: output.speaker\n\tDescription: MacBook Pro Speakers\n"
            ),
            subprocess.CompletedProcess([], 0),  # set-default-sink
            subprocess.CompletedProcess(
                [], 0,
                stdout=b"Name: input.mic\n\tDescription: MacBook Pro Microphone\n"
            ),
            subprocess.CompletedProcess([], 0),  # set-default-source
        ]

        sink, source = sync_pulseaudio_defaults("MacBook Pro Speakers", "MacBook Pro Microphone")

        assert sink == "output.speaker"
        assert source == "input.mic"

    def test_returns_none_when_no_match(self, mocker):
        """Returns None when no matching device found."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout=b"Name: other.device\n\tDescription: Other Device\n"
        )

        sink, source = sync_pulseaudio_defaults("MacBook Pro Speakers", "MacBook Pro Microphone")

        assert sink is None
        assert source is None


class TestGetGitConfig:
    """Test git config retrieval."""

    def test_returns_config_values(self, mocker):
        """Returns git user name and email."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout=b"Test User\n"),
            subprocess.CompletedProcess([], 0, stdout=b"test@example.com\n"),
        ]

        config = get_git_config()

        assert config["user_name"] == "Test User"
        assert config["user_email"] == "test@example.com"

    def test_returns_none_for_missing_config(self, mocker):
        """Returns None for missing config values."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 1, stdout=b"")

        config = get_git_config()

        assert config["user_name"] is None
        assert config["user_email"] is None


class TestValidateGithubRequirements:
    """Test GitHub access requirements validation."""

    def test_valid_when_all_present(self, mocker):
        """Returns success when all requirements met."""
        mocker.patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/ssh-agent.sock"})
        git_config = {"user_name": "Test User", "user_email": "test@example.com"}

        valid, errors = validate_github_requirements(git_config)

        assert valid is True
        assert errors == []

    def test_invalid_when_no_ssh_agent(self, mocker):
        """Returns error when SSH agent not running."""
        mocker.patch.dict(os.environ, {}, clear=True)
        # Make sure SSH_AUTH_SOCK is not in env
        if "SSH_AUTH_SOCK" in os.environ:
            del os.environ["SSH_AUTH_SOCK"]
        git_config = {"user_name": "Test User", "user_email": "test@example.com"}

        valid, errors = validate_github_requirements(git_config)

        assert valid is False
        assert any("SSH" in err for err in errors)

    def test_invalid_when_missing_git_name(self, mocker):
        """Returns error when git user.name not set."""
        mocker.patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/ssh.sock"})
        git_config = {"user_name": None, "user_email": "test@example.com"}

        valid, errors = validate_github_requirements(git_config)

        assert valid is False
        assert any("user.name" in err for err in errors)

    def test_invalid_when_missing_git_email(self, mocker):
        """Returns error when git user.email not set."""
        mocker.patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/ssh.sock"})
        git_config = {"user_name": "Test User", "user_email": None}

        valid, errors = validate_github_requirements(git_config)

        assert valid is False
        assert any("user.email" in err for err in errors)
