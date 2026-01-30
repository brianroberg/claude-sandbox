"""Tests for CLI argument parsing."""

import pytest

from claude_sandbox.args import Args, parse_args


class TestParseArgsDefaults:
    """Test default argument values."""

    def test_no_args_returns_defaults(self):
        """With no arguments, returns default profile and flags."""
        args = parse_args([])

        assert args.profile == "default"
        assert args.enable_github is False
        assert args.detach_mode is False
        assert args.host_ports == []
        assert args.command == []


class TestParseArgsProfile:
    """Test profile name parsing."""

    def test_single_arg_sets_profile(self):
        """A single positional argument sets the profile name."""
        args = parse_args(["work"])

        assert args.profile == "work"

    def test_profile_with_special_chars(self):
        """Profile names can contain hyphens and underscores."""
        args = parse_args(["my-work_profile"])

        assert args.profile == "my-work_profile"


class TestParseArgsGithub:
    """Test --github flag parsing."""

    def test_github_flag_enables_github(self):
        """--github flag enables GitHub access."""
        args = parse_args(["--github"])

        assert args.enable_github is True
        assert args.profile == "default"

    def test_github_with_profile(self):
        """--github can be combined with a profile name."""
        args = parse_args(["--github", "work"])

        assert args.enable_github is True
        assert args.profile == "work"

    def test_profile_then_github(self):
        """Profile can come before --github."""
        args = parse_args(["work", "--github"])

        assert args.enable_github is True
        assert args.profile == "work"


class TestParseArgsDetach:
    """Test --detach/-d flag parsing."""

    def test_detach_long_flag(self):
        """--detach flag enables detached mode."""
        args = parse_args(["--detach"])

        assert args.detach_mode is True

    def test_detach_short_flag(self):
        """-d flag enables detached mode."""
        args = parse_args(["-d"])

        assert args.detach_mode is True

    def test_detach_with_profile(self):
        """Detach can be combined with profile."""
        args = parse_args(["-d", "work"])

        assert args.detach_mode is True
        assert args.profile == "work"


class TestParseArgsHostPort:
    """Test --host-port flag parsing."""

    def test_single_host_port(self):
        """--host-port adds a port to the list."""
        args = parse_args(["--host-port", "8080"])

        assert args.host_ports == [8080]

    def test_multiple_host_ports(self):
        """Multiple --host-port flags accumulate."""
        args = parse_args(["--host-port", "8080", "--host-port", "3000"])

        assert args.host_ports == [8080, 3000]

    def test_host_port_missing_value_raises(self):
        """--host-port without a value raises an error."""
        with pytest.raises(SystemExit):
            parse_args(["--host-port"])

    def test_host_port_invalid_value_raises(self):
        """--host-port with non-numeric value raises an error."""
        with pytest.raises(SystemExit):
            parse_args(["--host-port", "abc"])

    def test_host_port_out_of_range_raises(self):
        """--host-port with port outside 1-65535 raises an error."""
        with pytest.raises(SystemExit):
            parse_args(["--host-port", "0"])

        with pytest.raises(SystemExit):
            parse_args(["--host-port", "65536"])

    def test_host_port_with_profile(self):
        """--host-port can be combined with profile."""
        args = parse_args(["--host-port", "8080", "work"])

        assert args.host_ports == [8080]
        assert args.profile == "work"


class TestParseArgsCommand:
    """Test command passthrough after --."""

    def test_double_dash_captures_command(self):
        """Everything after -- becomes the command."""
        args = parse_args(["--", "/bin/bash"])

        assert args.command == ["/bin/bash"]
        assert args.profile == "default"

    def test_double_dash_with_multiple_args(self):
        """Multiple args after -- are captured."""
        args = parse_args(["--", "echo", "hello", "world"])

        assert args.command == ["echo", "hello", "world"]

    def test_profile_then_command(self):
        """Profile can come before --."""
        args = parse_args(["work", "--", "/bin/bash"])

        assert args.profile == "work"
        assert args.command == ["/bin/bash"]

    def test_all_options_with_command(self):
        """All options can be combined with command."""
        args = parse_args(
            ["--github", "-d", "--host-port", "8080", "work", "--", "/bin/bash", "-c", "ls"]
        )

        assert args.enable_github is True
        assert args.detach_mode is True
        assert args.host_ports == [8080]
        assert args.profile == "work"
        assert args.command == ["/bin/bash", "-c", "ls"]


class TestParseArgsUnknownFlags:
    """Test handling of unknown flags."""

    def test_unknown_flag_passed_to_command(self):
        """Unknown flags (like -v) are passed through as command args."""
        args = parse_args(["-v"])

        assert args.command == ["-v"]

    def test_unknown_flag_with_profile_first(self):
        """Profile can come before unknown flags."""
        args = parse_args(["work", "-v", "--verbose"])

        assert args.profile == "work"
        assert args.command == ["-v", "--verbose"]


class TestArgsDataclass:
    """Test the Args dataclass."""

    def test_args_has_expected_fields(self):
        """Args dataclass has all expected fields."""
        args = Args(
            profile="test",
            enable_github=True,
            detach_mode=True,
            host_ports=[8080, 3000],
            command=["bash"],
        )

        assert args.profile == "test"
        assert args.enable_github is True
        assert args.detach_mode is True
        assert args.host_ports == [8080, 3000]
        assert args.command == ["bash"]

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
