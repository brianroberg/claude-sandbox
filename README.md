# Claude Code Sandbox

A Docker-based sandboxed environment for running Claude Code with voice mode (via AirPods) but no access to your Mac's filesystem or local network.

## What It Does

- Runs Claude Code inside an isolated Docker container
- Voice mode uses your Mac's Metal GPU for Whisper (STT) and Kokoro (TTS) via network
- Forwards audio (mic + speakers) from your Mac via PulseAudio over TCP
- Blocks all access to your local network (LAN)
- Allows public internet access
- Supports multiple named profiles with separate persistent storage
- Drops root privileges after setting up the firewall
- Optional GitHub access via SSH agent forwarding (private key stays on host)

## Quick Start

```bash
claude-sandbox                      # default profile (no GitHub access)
claude-sandbox work                 # isolated "work" environment
claude-sandbox --github             # default profile with GitHub access
claude-sandbox --github work        # "work" profile with GitHub access
claude-sandbox --host-port 8080     # allow access to host port 8080
claude-sandbox --host-port 8080 work # "work" profile with host port
```

**Caution:** The default command runs `claude --dangerously-skip-permissions`, which allows Claude to execute tools without asking for confirmation. This is the intended trade-off of a sandboxed environment — the container has no access to your filesystem or local network, so the permission prompts are less necessary. If you prefer the standard permission model, override with:

```bash
claude-sandbox work -- claude
```

Arguments after `--` replace the default command entirely:

```bash
claude-sandbox work -- /bin/bash       # get a shell instead of Claude Code
claude-sandbox work -- claude --help   # run claude with specific flags
```

To open a second shell in an already-running container:

```bash
docker exec -it -u claude claude-sandbox-work /bin/bash
```

### Voice Mode

The VoiceMode plugin is automatically installed on first startup (after you've authenticated Claude Code). If auto-install fails (e.g., on first launch before auth), it will retry on subsequent startups.

To verify the plugin is installed, run `/mcp` inside Claude Code — you should see `voicemode` listed and connected.

**Manual installation (if needed):**

```bash
claude plugin marketplace add mbailey/plugins
claude plugin install voicemode@mbailey
```

Plugin configuration persists in the profile's volume.

## Installation

The launch script is a Python package. Install it with [uv](https://docs.astral.sh/uv/):

```bash
cd ~/claude-sandbox
uv sync
```

Then run with:

```bash
uv run claude-sandbox [options] [profile]
```

Or install globally:

```bash
uv tool install ~/claude-sandbox
claude-sandbox [options] [profile]
```

## Files

All files live in `~/claude-sandbox/`:

| File | Purpose |
|------|---------|
| `Dockerfile` | Container image definition (Ubuntu 24.04 + dev tools) |
| `entrypoint.sh` | Firewall setup, capability drop, user switch |
| `src/claude_sandbox/` | Python package (CLI, Docker ops, audio/GitHub setup) |
| `tests/` | Unit and functional tests (76 tests) |
| `setup-host-audio.sh` | One-time PulseAudio setup on your Mac |
| `verify-sandbox.sh` | Run inside container to test isolation |

## What's Installed in the Container

- **Languages:** Node.js 22, Python 3.12
- **Package managers:** npm, pip, uv/uvx
- **Dev tools:** git, GitHub CLI (gh), build-essential (gcc, g++, make), vim, jq, curl, wget
- **Voice mode:** VoiceMode Python package (pre-configured for host services)
- **Audio:** PulseAudio client (connects to host over TCP)
- **Claude Code:** Latest version via native installer (rebuild image to update)

## Architecture

```
macOS Host                          Docker Container
-----------                         ----------------
AirPods (Bluetooth)                 Claude Code + VoiceMode MCP
    |                                   |
CoreAudio                          libpulse (client)
    |                                   |
PulseAudio daemon     <--- TCP:4713 --->  (audio I/O)
(port 4713)
                                        |
Whisper (STT)         <--- TCP:2022 --->  (speech recognition)
  Metal GPU
                                        |
Kokoro (TTS)          <--- TCP:8880 --->  (speech synthesis)
  Metal GPU
```

Voice mode runs inside the container but delegates GPU-intensive work (speech recognition and synthesis) to services running on your Mac with Metal acceleration. Only lightweight network calls cross the container boundary.

## Network Isolation

The container's firewall (set via iptables in the entrypoint) enforces:

| Destination | Allowed? |
|-------------|----------|
| Public internet | Yes |
| Host PulseAudio (port 4713) | Yes |
| Host Whisper STT (port 2022) | Yes |
| Host Kokoro TTS (port 8880) | Yes |
| Custom host ports (via `--host-port`) | Yes |
| DNS servers (Docker-configured) | Yes |
| Local network (192.168.x.x, 10.x.x.x, 172.16.x.x) | Blocked |
| Other host ports | Blocked |
| Link-local (169.254.x.x) | Blocked |

After the firewall rules are set, the process drops to the unprivileged `claude` user who cannot modify the rules.

### Opening Custom Host Ports

By default, the container can only access specific ports on the host (PulseAudio, Whisper, Kokoro). If you're developing agents or services that need to communicate with a service running on your Mac, use the `--host-port` flag:

```bash
claude-sandbox --host-port 8080                     # single port
claude-sandbox --host-port 8080 --host-port 9000    # multiple ports
claude-sandbox --host-port 8080 work                # with profile
```

Inside the container, connect to the host service via `host.docker.internal`:

```bash
curl http://host.docker.internal:8080
```

This is useful for:
- Testing agents that interact with local MCP servers
- Developing services that communicate with databases running on the host
- Any workflow requiring container-to-host communication on specific ports

## GitHub Access

By default, containers have no GitHub access — they can't push or pull from private repos, and git commits won't have your identity. This is intentional: most sandbox sessions don't need GitHub, and keeping credentials out reduces risk.

Use the `--github` flag to enable GitHub access:

```bash
claude-sandbox --github
claude-sandbox --github work
```

### How It Works

- **SSH Agent Forwarding:** Your private SSH key stays on your Mac. Docker forwards the SSH agent socket into the container, so `git` operations authenticate without copying your key.
- **Git Identity:** Your `user.name` and `user.email` are read from your Mac's `~/.gitconfig` and passed as environment variables.

### Prerequisites

Before using `--github`, ensure your Mac has:

1. **Git config set:**
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```

2. **SSH key added to your agent:**
   ```bash
   ssh-add ~/.ssh/your_github_key
   ```

   On macOS, the SSH agent usually runs automatically. You may need to re-add your key after a reboot (or configure your keychain to persist it).

3. **SSH key registered with GitHub:** The public key must be added to your GitHub account at https://github.com/settings/keys.

### Verifying GitHub Access

Inside a `--github` container:

```bash
# Test SSH connection to GitHub
ssh -T git@github.com

# Check git identity
git config user.name
git config user.email

# Clone a private repo
git clone git@github.com:yourname/private-repo.git
```

## Persistent Storage

Each profile gets a Docker named volume:

- `claude-sandbox-default` for the default profile
- `claude-sandbox-work` for the "work" profile
- etc.

The volume stores `/home/claude`, which includes:
- Claude Code auth tokens (OAuth login persists across sessions)
- Voice mode plugin configuration
- Shell history
- Any config files or dotfiles you create
- Files in the home directory

System-level packages installed with `apt-get` do NOT persist (by design).

### Managing Volumes

```bash
# List all sandbox volumes
docker volume ls | grep claude-sandbox

# Wipe a profile's storage
docker volume rm claude-sandbox-work

# Wipe all profiles
docker volume ls -q | grep claude-sandbox | xargs docker volume rm
```

## Host Services Setup

### PulseAudio (audio forwarding)

Audio forwarding requires PulseAudio running on your Mac. Run `setup-host-audio.sh` for initial setup.

Auto-start at login (recommended):

```bash
brew services start pulseaudio
```

The launch script will try to start PulseAudio automatically if it's not running.

**Important:** Only one PulseAudio instance should be running. Multiple instances cause audio routing problems (the container connects to whichever instance owns TCP port 4713, which may not be the one with your current configuration). If audio routes to the wrong device, check for duplicate processes:

```bash
ps aux | grep pulseaudio | grep -v grep
```

If you see more than one, kill all and restart:

```bash
pulseaudio --kill; sleep 1; pulseaudio --exit-idle-time=-1 --daemon
```

### Whisper & Kokoro (voice mode GPU services)

Whisper (STT) and Kokoro (TTS) must be running on your Mac for voice mode. These are installed via the `voicemode` CLI:

```bash
voicemode whisper service start
voicemode kokoro start
```

Check status:

```bash
voicemode whisper service status    # should show port 2022, Metal GPU
voicemode kokoro status             # should show port 8880
```

The container is pre-configured to connect to these services at `host.docker.internal:2022` and `host.docker.internal:8880` via environment variables:

- `VOICEMODE_STT_BASE_URLS=http://host.docker.internal:2022/v1`
- `VOICEMODE_TTS_BASE_URLS=http://host.docker.internal:8880/v1`

### Audio Device Routing

The launch script automatically syncs PulseAudio's default output and input devices with whatever macOS is currently using (e.g., AirPods, laptop speakers). This requires `SwitchAudioSource`:

```bash
brew install switchaudio-osx
```

The PulseAudio configuration (`~/.pulse/default.pa`) also includes:

- **`module-switch-on-connect`** — automatically switches to newly connected audio devices mid-session (e.g., when AirPods connect after PulseAudio is already running).
- **`module-stream-restore restore_device=false`** — prevents PulseAudio from remembering per-application device associations, so streams always follow the current default device.

### Troubleshooting Audio

1. **No audio devices in container:** Check that PulseAudio is running on your Mac (`pulseaudio --check`).

2. **Connection refused:** Verify TCP port 4713 is listening (`lsof -PiTCP:4713 -sTCP:LISTEN`).

3. **Firewall prompt:** macOS may ask to allow PulseAudio to accept incoming connections. Click "Allow."

4. **Microphone not working:** Ensure your Terminal app has Microphone permission in System Settings > Privacy & Security > Microphone.

5. **Wrong audio device:** The launch script should handle this automatically via `SwitchAudioSource`. If it doesn't, set the default manually:
   ```bash
   pactl list sinks short          # list output devices
   pactl set-default-sink <name>   # set default output
   pactl list sources short        # list input devices
   pactl set-default-source <name> # set default input
   ```

6. **Audio plays through wrong device despite correct defaults:** Check for multiple PulseAudio instances (see PulseAudio section above). The container connects via TCP and may reach a stale instance.

7. **No audio playback at all:** If `PULSE_SINK` or `PULSE_SOURCE` environment variables are set to a device name that PulseAudio can't resolve, playback silently fails. The launch script does not set these variables — if they are set in your shell environment, unset them.

8. **Voice mode can't reach Whisper/Kokoro:** Ensure the services are running on your Mac and ports 2022/8880 are accessible.

9. **Voice playback is slow and low-pitched:** This is a sample rate mismatch, typically caused by disconnecting and reconnecting Bluetooth audio (e.g., AirPods). Restart PulseAudio on your Mac and then restart the container:
   ```bash
   pulseaudio --kill; sleep 1; pulseaudio --exit-idle-time=-1 --daemon
   ```

## Rebuilding the Image

After editing the Dockerfile:

```bash
docker build -t claude-sandbox ~/claude-sandbox
```

## Authentication

Inside the container, Claude Code will prompt you to log in via OAuth (browser-based). The auth token is stored in the persistent volume, so you only need to log in once per profile.

Alternatively, set `ANTHROPIC_API_KEY` in your shell environment before launching, and it will be passed into the container.

## Requirements

- macOS with Docker Desktop
- Python 3.14+ and [uv](https://docs.astral.sh/uv/) (`brew install uv`)
- Homebrew (for PulseAudio and SwitchAudioSource)
- `switchaudio-osx` (`brew install switchaudio-osx`) — for automatic audio device detection
- Whisper and Kokoro services running on your Mac (for voice mode)
- An Anthropic account or API key

## Development

Run tests:

```bash
uv run pytest
```

Lint:

```bash
uv run ruff check src/ tests/
```
