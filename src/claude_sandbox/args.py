"""CLI argument parsing for claude-sandbox."""

import argparse
from dataclasses import dataclass, field


@dataclass
class Args:
    """Parsed command-line arguments."""

    profile: str = "default"
    enable_github: bool = False
    detach_mode: bool = False
    host_ports: list[int] = field(default_factory=list)
    command: list[str] = field(default_factory=list)

    @property
    def volume_name(self) -> str:
        """Docker volume name for this profile."""
        return f"claude-sandbox-{self.profile}"

    @property
    def workspace_volume_name(self) -> str:
        """Docker workspace volume name for this profile."""
        return f"claude-sandbox-{self.profile}-workspace"

    @property
    def container_name(self) -> str:
        """Docker container name for this profile."""
        return f"claude-sandbox-{self.profile}"


def _validate_port(value: str) -> int:
    """Validate and convert port string to int."""
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid port '{value}'. Must be 1-65535.") from None
    if port < 1 or port > 65535:
        raise argparse.ArgumentTypeError(f"Invalid port '{value}'. Must be 1-65535.")
    return port


def _create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="claude-sandbox",
        description="Launch Claude Code in a sandboxed Docker container",
        add_help=False,  # Don't fail on unknown args like -h passed to claude
    )
    parser.add_argument(
        "--github",
        action="store_true",
        dest="enable_github",
        help="Enable GitHub access via SSH agent forwarding",
    )
    parser.add_argument(
        "--detach", "-d",
        action="store_true",
        dest="detach_mode",
        help="Start container in background and return to host shell",
    )
    parser.add_argument(
        "--host-port",
        type=_validate_port,
        action="append",
        dest="host_ports",
        default=[],
        metavar="PORT",
        help="Allow container to connect to specified port on host (can be repeated)",
    )
    parser.add_argument(
        "profile",
        nargs="?",
        default="default",
        help="Profile name for isolated environment (default: 'default')",
    )
    return parser


def _split_at_unknown_flag_or_double_dash(argv: list[str]) -> tuple[list[str], list[str]]:
    """Split argv into known args and command args.

    Returns args before unknown flags (or --), and args after.
    """
    known_flags = {"--github", "--detach", "-d", "--host-port"}

    # Split at -- if present
    if "--" in argv:
        idx = argv.index("--")
        return argv[:idx], argv[idx + 1:]

    # Find first unknown flag or second positional arg
    profile_found = False
    i = 0
    while i < len(argv):
        arg = argv[i]

        if arg == "--host-port":
            # Skip --host-port and its value
            i += 2
            continue

        if arg.startswith("-"):
            if arg not in known_flags:
                # Unknown flag - rest goes to command
                return argv[:i], argv[i:]
            i += 1
            continue

        # Positional argument
        if profile_found:
            # Second positional - rest goes to command
            return argv[:i], argv[i:]
        profile_found = True
        i += 1

    return argv, []


def parse_args(argv: list[str]) -> Args:
    """Parse command-line arguments.

    Args:
        argv: List of command-line arguments (without the program name).

    Returns:
        Parsed Args object.

    Raises:
        SystemExit: On invalid arguments.
    """
    parser = _create_parser()

    # Split at unknown flags or --
    pre_args, command_args = _split_at_unknown_flag_or_double_dash(argv)

    try:
        parsed, remaining = parser.parse_known_args(pre_args)
    except SystemExit:
        # Re-raise for invalid args (like invalid port)
        raise

    # Any remaining args from parse_known_args go to command
    if remaining:
        command_args = remaining + command_args

    return Args(
        profile=parsed.profile or "default",
        enable_github=parsed.enable_github,
        detach_mode=parsed.detach_mode,
        host_ports=parsed.host_ports or [],
        command=command_args,
    )
