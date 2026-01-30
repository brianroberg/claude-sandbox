"""System operations for audio and GitHub setup."""

import os
import subprocess


def check_pulseaudio_running() -> bool:
    """Check if PulseAudio is running."""
    result = subprocess.run(
        ["pulseaudio", "--check"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def start_pulseaudio() -> bool:
    """Start PulseAudio daemon.

    Returns:
        True if started successfully, False otherwise.
    """
    result = subprocess.run(
        ["pulseaudio", "--exit-idle-time=-1", "--daemon"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def get_macos_audio_devices() -> tuple[str | None, str | None]:
    """Get current macOS audio devices using SwitchAudioSource.

    Returns:
        Tuple of (output_device, input_device), or (None, None) if unavailable.
    """
    try:
        # Get output device
        output_result = subprocess.run(
            ["SwitchAudioSource", "-c"],
            capture_output=True,
            check=False,
        )
        output = None
        if output_result.returncode == 0 and output_result.stdout:
            output = output_result.stdout.decode().strip()

        # Get input device
        input_result = subprocess.run(
            ["SwitchAudioSource", "-c", "-t", "input"],
            capture_output=True,
            check=False,
        )
        input_dev = None
        if input_result.returncode == 0 and input_result.stdout:
            input_dev = input_result.stdout.decode().strip()

        return output, input_dev
    except FileNotFoundError:
        return None, None


def _find_pulseaudio_device(
    device_type: str,
    description: str,
) -> str | None:
    """Find a PulseAudio device by description.

    Args:
        device_type: "sinks" or "sources"
        description: Device description to match

    Returns:
        Device name or None if not found.
    """
    result = subprocess.run(
        ["pactl", "list", device_type],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None

    output = result.stdout.decode()
    # Parse pactl output to find device name by description
    # Format:
    # Name: device.name
    # ...
    # Description: Device Description

    lines = output.split("\n")
    current_name = None

    for line in lines:
        line = line.strip()
        if line.startswith("Name:"):
            current_name = line.split(":", 1)[1].strip()
        elif line.startswith("Description:"):
            desc = line.split(":", 1)[1].strip()
            if desc == description:
                # For sources, skip .monitor entries
                if device_type == "sources" and current_name and ".monitor" in current_name:
                    continue
                return current_name

    return None


def sync_pulseaudio_defaults(
    output_device: str | None,
    input_device: str | None,
) -> tuple[str | None, str | None]:
    """Sync PulseAudio defaults with macOS audio devices.

    Returns:
        Tuple of (sink_name, source_name) that were set, or None if not found.
    """
    sink = None
    source = None

    if output_device:
        sink = _find_pulseaudio_device("sinks", output_device)
        if sink:
            subprocess.run(
                ["pactl", "set-default-sink", sink],
                capture_output=True,
                check=False,
            )

    if input_device:
        source = _find_pulseaudio_device("sources", input_device)
        if source:
            subprocess.run(
                ["pactl", "set-default-source", source],
                capture_output=True,
                check=False,
            )

    return sink, source


def get_git_config() -> dict[str, str | None]:
    """Get git global config values.

    Returns:
        Dict with user_name and user_email, values may be None if not set.
    """
    def get_config_value(key: str) -> str | None:
        result = subprocess.run(
            ["git", "config", "--global", key],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode().strip()
        return None

    return {
        "user_name": get_config_value("user.name"),
        "user_email": get_config_value("user.email"),
    }


def validate_github_requirements(
    git_config: dict[str, str | None],
) -> tuple[bool, list[str]]:
    """Validate requirements for GitHub access.

    Args:
        git_config: Dict from get_git_config()

    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors: list[str] = []

    # Check SSH agent
    ssh_sock = os.environ.get("SSH_AUTH_SOCK")
    if not ssh_sock:
        errors.append(
            "SSH agent not running. Start it with:\n"
            "  eval $(ssh-agent -s)\n"
            "  ssh-add ~/.ssh/your_github_key"
        )

    # Check git config
    if not git_config.get("user_name"):
        errors.append(
            'git config user.name not set. Run: git config --global user.name "Your Name"'
        )

    if not git_config.get("user_email"):
        errors.append(
            'git config user.email not set. Run: git config --global user.email "you@example.com"'
        )

    return len(errors) == 0, errors
