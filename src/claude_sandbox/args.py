"""CLI argument parsing for claude-sandbox."""

from dataclasses import dataclass, field


@dataclass
class Args:
    """Parsed command-line arguments."""

    profile: str = "default"
    enable_github: bool = False
    detach_mode: bool = False
    host_ports: list[int] = field(default_factory=list)

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
