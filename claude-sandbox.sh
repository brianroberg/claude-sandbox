#!/bin/bash
# ============================================================
# Launch Claude Code in a sandboxed Docker container
# with audio forwarding and network isolation.
#
# Usage: claude-sandbox [profile] [-- claude-args...]
#   profile:     Optional name for an isolated environment.
#                Each profile gets its own persistent storage.
#                Defaults to "default".
#   claude-args: Arguments passed through to the claude command
#                (everything after --).
#
# Examples:
#   claude-sandbox                    # default profile
#   claude-sandbox work               # "work" profile
#   claude-sandbox personal           # "personal" profile
#   claude-sandbox work -- --help     # pass flags to claude
# ============================================================

set -euo pipefail

IMAGE_NAME="claude-sandbox"

# Parse profile name (first arg, if it doesn't start with -)
PROFILE="default"
CLAUDE_ARGS=()

if [ $# -gt 0 ]; then
    if [ "$1" = "--" ]; then
        shift
        CLAUDE_ARGS=("$@")
    elif [[ "$1" != -* ]]; then
        PROFILE="$1"
        shift
        if [ $# -gt 0 ] && [ "$1" = "--" ]; then
            shift
        fi
        CLAUDE_ARGS=("$@")
    else
        CLAUDE_ARGS=("$@")
    fi
fi

VOLUME_NAME="claude-sandbox-${PROFILE}"
CONTAINER_NAME="claude-sandbox-${PROFILE}"

# Ensure the persistent volume exists
docker volume inspect "$VOLUME_NAME" &>/dev/null || {
    echo "Creating persistent volume '$VOLUME_NAME' for profile '$PROFILE'..."
    docker volume create "$VOLUME_NAME"
}

# Ensure PulseAudio is running on the host
if ! pulseaudio --check 2>/dev/null; then
    echo "PulseAudio is not running. Starting it..."
    pulseaudio --exit-idle-time=-1 --daemon 2>/dev/null || {
        echo "ERROR: Could not start PulseAudio."
        echo "Run setup-host-audio.sh first."
        exit 1
    }
fi

# Check if the Docker image exists; build if not
if ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "Docker image '$IMAGE_NAME' not found. Building..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"
fi

# Sync PulseAudio defaults with macOS active audio devices and
# pass explicit sink/source to the container as client-side overrides
PA_SINK=""
PA_SOURCE=""
if command -v SwitchAudioSource &>/dev/null; then
    MACOS_OUTPUT=$(SwitchAudioSource -c 2>/dev/null)
    MACOS_INPUT=$(SwitchAudioSource -c -t input 2>/dev/null)

    if [ -n "$MACOS_OUTPUT" ]; then
        PA_SINK=$(pactl list sinks 2>/dev/null \
            | grep -B1 "Description: ${MACOS_OUTPUT}$" \
            | awk '/Name:/ {print $2}')
        if [ -n "$PA_SINK" ]; then
            pactl set-default-sink "$PA_SINK" 2>/dev/null
            echo "Audio output: $MACOS_OUTPUT"
        fi
    fi

    if [ -n "$MACOS_INPUT" ]; then
        # Match real sources only (exclude .monitor entries)
        PA_SOURCE=$(pactl list sources 2>/dev/null \
            | grep -B1 "Description: ${MACOS_INPUT}$" \
            | awk '/Name:/ {print $2}' \
            | grep -v '\.monitor$' \
            | head -1)
        if [ -n "$PA_SOURCE" ]; then
            pactl set-default-source "$PA_SOURCE" 2>/dev/null
            echo "Audio input:  $MACOS_INPUT"
        fi
    fi
fi

echo "Launching Claude sandbox (profile: $PROFILE)"

# Launch the container
exec docker run -it --rm \
    --cap-add=NET_ADMIN \
    --add-host=host.docker.internal:host-gateway \
    -v "$VOLUME_NAME":/home/claude \
    -e PULSE_SERVER=tcp:host.docker.internal:4713 \
    -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    -e TERM="$TERM" \
    --hostname "$CONTAINER_NAME" \
    --name "$CONTAINER_NAME" \
    "$IMAGE_NAME" \
    claude ${CLAUDE_ARGS[@]+"${CLAUDE_ARGS[@]}"}
