"""Tests for Args dataclass."""

from claude_sandbox.args import Args


class TestArgsDataclass:
    """Test the Args dataclass."""

    def test_args_has_expected_fields(self):
        """Args dataclass has all expected fields."""
        args = Args(
            profile="test",
            enable_github=True,
            detach_mode=True,
            host_ports=[8080, 3000],
        )

        assert args.profile == "test"
        assert args.enable_github is True
        assert args.detach_mode is True
        assert args.host_ports == [8080, 3000]

    def test_args_defaults(self):
        """Args has sensible defaults."""
        args = Args()

        assert args.profile == "default"
        assert args.enable_github is False
        assert args.detach_mode is False
        assert args.host_ports == []

    def test_volume_name_property(self):
        """Args has a volume_name property."""
        args = Args(profile="work")

        assert args.volume_name == "claude-sandbox-work"

    def test_workspace_volume_name_property(self):
        """Args has a workspace_volume_name property."""
        args = Args(profile="work")

        assert args.workspace_volume_name == "claude-sandbox-work-workspace"

    def test_container_name_property(self):
        """Args has a container_name property."""
        args = Args(profile="work")

        assert args.container_name == "claude-sandbox-work"
