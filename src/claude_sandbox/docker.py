"""Docker operations for claude-sandbox."""

import subprocess


def ensure_volume_exists(volume_name: str) -> bool:
    """Ensure a Docker volume exists, creating it if necessary.

    Returns:
        True if volume exists or was created successfully, False otherwise.
    """
    # Check if volume exists
    result = subprocess.run(
        ["docker", "volume", "inspect", volume_name],
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return True

    # Volume doesn't exist, create it
    result = subprocess.run(
        ["docker", "volume", "create", volume_name],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def check_image_exists(image_name: str) -> bool:
    """Check if a Docker image exists."""
    result = subprocess.run(
        ["docker", "image", "inspect", image_name],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def build_image(image_name: str, context_path: str) -> bool:
    """Build a Docker image.

    Returns:
        True if build succeeded, False otherwise.
    """
    result = subprocess.run(
        ["docker", "build", "-t", image_name, context_path],
        check=False,
    )
    return result.returncode == 0


def check_container_exists(container_name: str) -> bool:
    """Check if a Docker container exists (running or stopped)."""
    result = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return False

    containers = result.stdout.decode().strip().split("\n")
    return container_name in containers


def build_docker_args(
    container_name: str,
    volume_name: str,
    workspace_volume_name: str,
    host_ports: list[int],
    enable_github: bool,
    github_config: dict[str, str] | None,
    api_key: str,
    term: str,
) -> list[str]:
    """Build Docker run command arguments."""
    args = [
        "--rm",
        "--cap-add=NET_ADMIN",
        "--add-host=host.docker.internal:host-gateway",
        "-v", f"{volume_name}:/home/claude",
        "-v", f"{workspace_volume_name}:/workspace",
        "-e", "PULSE_SERVER=tcp:host.docker.internal:4713",
        "-e", f"ANTHROPIC_API_KEY={api_key}",
        "-e", f"TERM={term}",
        "-e", f"HOST_PORTS={' '.join(str(p) for p in host_ports)}",
        "--hostname", container_name,
        "--name", container_name,
    ]

    if enable_github and github_config:
        args.extend([
            "-v", "/run/host-services/ssh-auth.sock:/run/host-services/ssh-auth.sock",
            "-e", "SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock",
            "-e", f"GIT_AUTHOR_NAME={github_config['user_name']}",
            "-e", f"GIT_AUTHOR_EMAIL={github_config['user_email']}",
            "-e", f"GIT_COMMITTER_NAME={github_config['user_name']}",
            "-e", f"GIT_COMMITTER_EMAIL={github_config['user_email']}",
        ])

    return args
