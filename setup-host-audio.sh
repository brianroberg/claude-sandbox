#!/bin/bash
set -euo pipefail

# ============================================================
# PulseAudio Host Setup for Docker Audio Forwarding
# Run this once on your Mac to enable audio in containers.
# ============================================================

echo "=== Setting up PulseAudio for Docker audio forwarding ==="
echo ""

# Step 1: Install PulseAudio via Homebrew
if ! command -v pulseaudio &>/dev/null; then
    echo "Installing PulseAudio..."
    brew install pulseaudio
else
    echo "PulseAudio already installed."
fi

BREW_PREFIX=$(brew --prefix)

# Step 2: Create user config directory
mkdir -p ~/.pulse

# Copy default configs if they don't exist yet
if [ ! -f ~/.pulse/default.pa ]; then
    PA_ETC="$BREW_PREFIX/etc/pulse"
    if [ ! -d "$PA_ETC" ]; then
        PA_ETC="$BREW_PREFIX/opt/pulseaudio/etc/pulse"
    fi
    cp -R "$PA_ETC/"* ~/.pulse/
    echo "Copied default PulseAudio configuration to ~/.pulse/"
else
    echo "PulseAudio config already exists at ~/.pulse/"
fi

# Step 3: Add TCP module if not already present
if ! grep -q "module-native-protocol-tcp" ~/.pulse/default.pa; then
    cat >> ~/.pulse/default.pa << 'EOF'

### Allow Docker containers to connect for audio
load-module module-native-protocol-tcp auth-ip-acl=127.0.0.0/8;10.0.0.0/8;172.16.0.0/12;192.168.0.0/16
EOF
    echo "Added TCP module to PulseAudio config."
else
    echo "TCP module already configured."
fi

# Step 4: Start (or restart) PulseAudio
pulseaudio --kill 2>/dev/null || true
sleep 1

pulseaudio --exit-idle-time=-1 --daemon --verbose
echo ""
echo "PulseAudio daemon started."

# Step 5: Verify
echo ""
echo "=== Verification ==="

if pulseaudio --check 2>/dev/null; then
    echo "PulseAudio: RUNNING"
else
    echo "PulseAudio: NOT RUNNING (check errors above)"
    exit 1
fi

echo ""
echo "Output devices (sinks):"
pactl list sinks short 2>/dev/null || echo "  (none found)"

echo ""
echo "Input devices (sources/microphones):"
pactl list sources short 2>/dev/null || echo "  (none found)"

echo ""
if lsof -PiTCP:4713 -sTCP:LISTEN &>/dev/null; then
    echo "TCP port 4713: LISTENING"
else
    echo "TCP port 4713: NOT LISTENING (Docker containers won't be able to connect)"
    exit 1
fi

echo ""
echo "=== Host audio setup complete ==="
echo ""
echo "NOTE: If macOS shows a firewall prompt for PulseAudio, click 'Allow'."
echo "NOTE: Ensure your Terminal app has Microphone permission in:"
echo "      System Settings > Privacy & Security > Microphone"
