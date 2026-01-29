#!/bin/bash
# ============================================================
# Launch Claude Code in a sandboxed Docker container
# with audio forwarding and network isolation.
#
# Usage: claude-sandbox [--github] [--detach|-d] [profile] [-- command...]
#   --github:    Enable GitHub access via SSH agent forwarding
#                and git config from host's ~/.gitconfig.
#   --detach|-d: Start container in background and return to host shell.
#                Container runs 'sleep infinity'; attach with docker exec.
#   profile:     Optional name for an isolated environment.
#                Each profile gets its own persistent storage.
#                Defaults to "default".
#   command:     Command to run instead of claude (everything after --).
#
# Examples:
#   claude-sandbox                    # default profile, no GitHub
#   claude-sandbox work               # "work" profile, no GitHub
#   claude-sandbox --github           # default profile with GitHub
#   claude-sandbox --github work      # "work" profile with GitHub
#   claude-sandbox -d work            # start detached, attach later
#   claude-sandbox work -- /bin/bash  # run shell instead of claude
# ============================================================

set -euo pipefail

IMAGE_NAME="claude-sandbox"

# Parse arguments: [--github] [--detach|-d] [profile] [-- command...]
PROFILE="default"
ENABLE_GITHUB=false
DETACH_MODE=false
CLAUDE_ARGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --github)
            ENABLE_GITHUB=true
            shift
            ;;
        --detach|-d)
            DETACH_MODE=true
            shift
            ;;
        --)
            shift
            CLAUDE_ARGS=("$@")
            break
            ;;
        -*)
            # Unknown flag - pass to claude
            CLAUDE_ARGS=("$@")
            break
            ;;
        *)
            # First non-flag arg is profile name
            if [ "$PROFILE" = "default" ]; then
                PROFILE="$1"
                shift
            else
                CLAUDE_ARGS=("$@")
                break
            fi
            ;;
    esac
done

VOLUME_NAME="claude-sandbox-${PROFILE}"
WORKSPACE_VOLUME_NAME="claude-sandbox-${PROFILE}-workspace"
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

# Check if container already exists (would cause naming conflict)
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container '$CONTAINER_NAME' already exists."
    echo "Stop it first with: docker stop $CONTAINER_NAME"
    exit 1
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

# Set up GitHub access if requested
GITHUB_DOCKER_ARGS=()
if [ "$ENABLE_GITHUB" = true ]; then
    # Read git config from host's ~/.gitconfig
    GIT_USER_NAME=$(git config --global user.name 2>/dev/null || true)
    GIT_USER_EMAIL=$(git config --global user.email 2>/dev/null || true)

    if [ -z "$GIT_USER_NAME" ] || [ -z "$GIT_USER_EMAIL" ]; then
        echo "ERROR: --github requires git config on host."
        echo "Run these commands first:"
        [ -z "$GIT_USER_NAME" ] && echo "  git config --global user.name \"Your Name\""
        [ -z "$GIT_USER_EMAIL" ] && echo "  git config --global user.email \"you@example.com\""
        exit 1
    fi

    # macOS Docker Desktop uses a special socket path for SSH agent forwarding
    if [ -z "${SSH_AUTH_SOCK:-}" ]; then
        echo "ERROR: SSH agent not running. Start it with:"
        echo "  eval \$(ssh-agent -s)"
        echo "  ssh-add ~/.ssh/your_github_key"
        exit 1
    fi

    GITHUB_DOCKER_ARGS=(
        -v /run/host-services/ssh-auth.sock:/run/host-services/ssh-auth.sock
        -e SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock
        -e GIT_AUTHOR_NAME="$GIT_USER_NAME"
        -e GIT_AUTHOR_EMAIL="$GIT_USER_EMAIL"
        -e GIT_COMMITTER_NAME="$GIT_USER_NAME"
        -e GIT_COMMITTER_EMAIL="$GIT_USER_EMAIL"
    )

    echo "GitHub access: enabled (git user: $GIT_USER_NAME <$GIT_USER_EMAIL>)"
fi

# Common Docker run arguments
DOCKER_ARGS=(
    --rm
    --cap-add=NET_ADMIN
    --add-host=host.docker.internal:host-gateway
    -v "$VOLUME_NAME":/home/claude
    -v "$WORKSPACE_VOLUME_NAME":/workspace
    -e PULSE_SERVER=tcp:host.docker.internal:4713
    -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
    -e TERM="$TERM"
    ${GITHUB_DOCKER_ARGS[@]+"${GITHUB_DOCKER_ARGS[@]}"}
    --hostname "$CONTAINER_NAME"
    --name "$CONTAINER_NAME"
)

# Launch the container
if [ "$DETACH_MODE" = true ]; then
    echo "Starting Claude sandbox in detached mode (profile: $PROFILE)"
    if ! docker run -d "${DOCKER_ARGS[@]}" "$IMAGE_NAME" sleep infinity >/dev/null; then
        echo "ERROR: Failed to start container."
        exit 1
    fi
    echo "Container '$CONTAINER_NAME' is running."
    echo ""
    echo "To use Claude:"
    echo "  docker exec -it -u claude $CONTAINER_NAME claude --dangerously-skip-permissions"
    echo ""
    echo "To open a shell:"
    echo "  docker exec -it -u claude $CONTAINER_NAME /bin/bash"
    echo ""
    echo "To stop:"
    echo "  docker stop $CONTAINER_NAME"
else
    echo "Launching Claude sandbox (profile: $PROFILE)"

    # Set up folder with container icon for Terminal.app title bar
    # The folder is named after the profile so Terminal shows just the profile name
    TITLE_DIR="/tmp/claude-sandbox/$PROFILE"
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    if [ ! -d "$TITLE_DIR" ]; then
        mkdir -p "$TITLE_DIR"
        npx -y fileicon set "$TITLE_DIR" "$SCRIPT_DIR/container.icns" 2>/dev/null || true
    fi

    # Set Terminal.app's working directory display to show container icon and profile name
    # (OSC 7 escape sequence with file: URL)
    printf '\033]7;file://localhost%s\007' "$TITLE_DIR"

    exec docker run -it "${DOCKER_ARGS[@]}" "$IMAGE_NAME" ${CLAUDE_ARGS[@]+"${CLAUDE_ARGS[@]}"}
fi
