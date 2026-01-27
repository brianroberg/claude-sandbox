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

## Quick Start

```bash
claude-sandbox                # default profile
claude-sandbox work           # isolated "work" environment
claude-sandbox experiments    # isolated "experiments" environment
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

### First-time Voice Mode Setup (once per profile)

Inside Claude Code, install the voice mode plugin:

1. Type `/mcp` to open MCP settings
2. Add the `mbailey` marketplace (source: GitHub, repo: `mbailey/plugins`)
3. Install the `voicemode` plugin
4. Restart Claude Code (`/exit` then relaunch)

This persists in the profile's volume -- you only do it once.

## Files

All files live in `~/claude-sandbox/`:

| File | Purpose |
|------|---------|
| `Dockerfile` | Container image definition (Ubuntu 24.04 + dev tools) |
| `entrypoint.sh` | Firewall setup, capability drop, user switch |
| `claude-sandbox.sh` | Launch script with profile support |
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
| DNS servers (Docker-configured) | Yes |
| Local network (192.168.x.x, 10.x.x.x, 172.16.x.x) | Blocked |
| Other host ports | Blocked |
| Link-local (169.254.x.x) | Blocked |

After the firewall rules are set, the process drops to the unprivileged `claude` user who cannot modify the rules.

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
- Homebrew (for PulseAudio and SwitchAudioSource)
- `switchaudio-osx` (`brew install switchaudio-osx`) — for automatic audio device detection
- Whisper and Kokoro services running on your Mac (for voice mode)
- An Anthropic account or API key
