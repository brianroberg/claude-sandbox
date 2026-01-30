"""CLI entry point for claude-sandbox."""

import os
import subprocess
import sys
from pathlib import Path

import click

from claude_sandbox.args import Args
from claude_sandbox.docker import (
    build_docker_args,
    build_image,
    check_container_exists,
    check_image_exists,
    ensure_volume_exists,
)
from claude_sandbox.system import (
    check_pulseaudio_running,
    get_git_config,
    get_macos_audio_devices,
    start_pulseaudio,
    sync_pulseaudio_defaults,
    validate_github_requirements,
)

IMAGE_NAME = "claude-sandbox"


def get_script_dir() -> str:
    """Get the directory containing the script/package."""
    # When installed as a package, use the package directory
    # When run directly, use the script's directory
    return str(Path(__file__).parent.parent.parent)


def run_sandbox(args: Args) -> None:
    """Run the Claude sandbox.

    Args:
        args: Parsed command-line arguments.
    """
    script_dir = get_script_dir()

    # Ensure PulseAudio is running
    if not check_pulseaudio_running():
        print("PulseAudio is not running. Starting it...")
        if not start_pulseaudio():
            print("ERROR: Could not start PulseAudio.", file=sys.stderr)
            print("Run setup-host-audio.sh first.", file=sys.stderr)
            sys.exit(1)

    # Check/build Docker image
    if not check_image_exists(IMAGE_NAME):
        print(f"Docker image '{IMAGE_NAME}' not found. Building...")
        if not build_image(IMAGE_NAME, script_dir):
            print("ERROR: Failed to build Docker image.", file=sys.stderr)
            sys.exit(1)

    # Check for existing container
    if check_container_exists(args.container_name):
        print(f"ERROR: Container '{args.container_name}' already exists.", file=sys.stderr)
        print(f"Stop it first with: docker stop {args.container_name}", file=sys.stderr)
        sys.exit(1)

    # Validate GitHub requirements if enabled
    github_config = None
    if args.enable_github:
        git_config = get_git_config()
        valid, errors = validate_github_requirements(git_config)
        if not valid:
            print("ERROR: --github requires additional configuration:", file=sys.stderr)
            for error in errors:
                print(f"  {error}", file=sys.stderr)
            sys.exit(1)
        github_config = git_config

    # Ensure volumes exist
    print(f"Creating persistent volume '{args.volume_name}' for profile '{args.profile}'...")
    if not ensure_volume_exists(args.volume_name):
        print(f"ERROR: Failed to create volume '{args.volume_name}'.", file=sys.stderr)
        sys.exit(1)
    if not ensure_volume_exists(args.workspace_volume_name):
        print(f"ERROR: Failed to create volume '{args.workspace_volume_name}'.", file=sys.stderr)
        sys.exit(1)

    # Sync audio devices
    output_dev, input_dev = get_macos_audio_devices()
    if output_dev or input_dev:
        sink, source = sync_pulseaudio_defaults(output_dev, input_dev)
        if sink:
            print(f"Audio output: {output_dev}")
        if source:
            print(f"Audio input: {input_dev}")

    if args.enable_github and github_config:
        print(
            f"GitHub access: enabled "
            f"(git user: {github_config['user_name']} <{github_config['user_email']}>)"
        )

    # Build Docker arguments
    docker_args = build_docker_args(
        container_name=args.container_name,
        volume_name=args.volume_name,
        workspace_volume_name=args.workspace_volume_name,
        host_ports=args.host_ports,
        enable_github=args.enable_github,
        github_config=github_config,
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        term=os.environ.get("TERM", "xterm-256color"),
    )

    # Build the command
    if args.detach_mode:
        print(f"Starting Claude sandbox in detached mode (profile: {args.profile})")
        cmd = ["docker", "run", "-d", *docker_args, IMAGE_NAME, "sleep", "infinity"]
        result = subprocess.run(cmd, capture_output=True, check=False)
        if result.returncode != 0:
            print("ERROR: Failed to start container.", file=sys.stderr)
            if result.stderr:
                print(result.stderr.decode().strip(), file=sys.stderr)
            sys.exit(1)
        print(f"Container '{args.container_name}' is running.")
        print()
        print("To use Claude:")
        print(f"  docker exec -it -u claude {args.container_name} claude \\")
        print("    --dangerously-skip-permissions")
        print()
        print("To open a shell:")
        print(f"  docker exec -it -u claude {args.container_name} /bin/bash")
        print()
        print("To stop:")
        print(f"  docker stop {args.container_name}")
    else:
        print(f"Launching Claude sandbox (profile: {args.profile})")
        cmd = ["docker", "run", "-it", *docker_args, IMAGE_NAME, "/bin/bash"]
        subprocess.run(cmd, check=False)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("profile", default="default", required=False)
@click.option(
    "--github",
    is_flag=True,
    help="Enable GitHub access via SSH agent forwarding",
)
@click.option(
    "--detach",
    "-d",
    is_flag=True,
    help="Start container in background and return to host shell",
)
@click.option(
    "--host-port",
    multiple=True,
    type=click.IntRange(1, 65535),
    metavar="PORT",
    help="Allow container to connect to specified port on host (can be repeated)",
)
def main(profile: str, github: bool, detach: bool, host_port: tuple[int, ...]) -> None:
    """Launch Claude Code in a sandboxed Docker container.

    PROFILE is the profile name for isolated environment (default: 'default').
    """
    args = Args(
        profile=profile,
        enable_github=github,
        detach_mode=detach,
        host_ports=list(host_port),
    )
    run_sandbox(args)
