#!/bin/bash
set -e

# ============================================================
# Network Firewall Setup
# Allows: DNS, PulseAudio on host, public internet
# Blocks: all other private/LAN traffic
# ============================================================

# Resolve host.docker.internal to an IPv4 address (getent may return IPv6)
HOST_IP=$(getent ahostsv4 host.docker.internal | awk 'NR==1{ print $1 }')
GATEWAY_IP=$(ip route | grep default | awk '{ print $3 }')

if [ -z "$HOST_IP" ]; then
    echo "WARNING: Could not resolve host.docker.internal. Audio may not work."
    HOST_IP="0.0.0.0"
fi

# Set default OUTPUT policy to DROP
iptables -P OUTPUT DROP 2>/dev/null || true

# Allow loopback
iptables -A OUTPUT -o lo -j ACCEPT

# Allow established/related return traffic
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow DNS to all nameservers configured by Docker (including Docker Desktop's
# internal DNS which may be on a private IP like 192.168.65.7)
for dns_ip in $(awk '/^nameserver/ { print $2 }' /etc/resolv.conf) 127.0.0.11 "$GATEWAY_IP"; do
    iptables -A OUTPUT -p udp --dport 53 -d "$dns_ip" -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -d "$dns_ip" -j ACCEPT
done

# Allow voice mode services on the host
# PulseAudio (audio forwarding): port 4713
# Whisper (STT, Metal GPU):      port 2022
# Kokoro (TTS, Metal GPU):       port 8880
# Plus any custom ports from --host-port flags
for port in 4713 2022 8880 ${HOST_PORTS:-}; do
    iptables -A OUTPUT -p tcp -d "$HOST_IP" --dport "$port" -j ACCEPT
done

# Block all private/link-local address ranges (LAN isolation)
iptables -A OUTPUT -d 10.0.0.0/8 -j DROP
iptables -A OUTPUT -d 172.16.0.0/12 -j DROP
iptables -A OUTPUT -d 192.168.0.0/16 -j DROP
iptables -A OUTPUT -d 169.254.0.0/16 -j DROP

# Allow everything else (public internet)
iptables -A OUTPUT -j ACCEPT

echo "Firewall configured:"
echo "  Host IP: $HOST_IP"
ALLOWED_PORTS="DNS, PulseAudio (:4713), Whisper (:2022), Kokoro (:8880)"
if [ -n "${HOST_PORTS:-}" ]; then
    ALLOWED_PORTS="$ALLOWED_PORTS, custom (:${HOST_PORTS// /, :})"
fi
echo "  Allowed: $ALLOWED_PORTS, public internet"
echo "  Blocked: all private/LAN ranges"
echo ""

# ============================================================
# First-run setup (persistent volume may be empty)
# ============================================================

# PulseAudio client config
mkdir -p /home/claude/.config/pulse
if [ ! -f /home/claude/.config/pulse/client.conf ]; then
    echo "enable-shm = false" > /home/claude/.config/pulse/client.conf
fi

# VoiceMode global config (points STT/TTS at host services)
mkdir -p /home/claude/.voicemode
if [ ! -f /home/claude/.voicemode/voicemode.env ]; then
    cat > /home/claude/.voicemode/voicemode.env << 'VMEOF'
VOICEMODE_STT_BASE_URLS=http://host.docker.internal:2022/v1
VOICEMODE_TTS_BASE_URLS=http://host.docker.internal:8880/v1
VOICEMODE_WHISPER_PORT=2022
VOICEMODE_KOKORO_PORT=8880
VOICEMODE_VOICES=af_river
VMEOF
fi

# Ensure claude user owns their home directory contents
chown -R claude:claude /home/claude

# Ensure workspace directory exists
mkdir -p /workspace
chown claude:claude /workspace

# Install VoiceMode plugin if not already done
# Uses a marker file since the plugin commands require auth (may fail on first run)
VOICEMODE_MARKER="/home/claude/.voicemode/.plugin-installed"
if [ ! -f "$VOICEMODE_MARKER" ]; then
    echo "Installing VoiceMode plugin..."
    if runuser -u claude -- claude plugin marketplace add mbailey/plugins 2>/dev/null; then
        if runuser -u claude -- claude plugin install voicemode@mbailey 2>/dev/null; then
            touch "$VOICEMODE_MARKER"
            chown claude:claude "$VOICEMODE_MARKER"
            echo "VoiceMode plugin installed successfully."
        else
            echo "Note: VoiceMode plugin install failed (auth may be required). Will retry next startup."
        fi
    else
        echo "Note: Could not add plugin marketplace (auth may be required). Will retry next startup."
    fi
fi

# Fix SSH agent socket permissions if mounted (for --github mode)
if [ -S /run/host-services/ssh-auth.sock ]; then
    chmod 666 /run/host-services/ssh-auth.sock
fi

# Drop to non-root user (non-root user cannot modify iptables)
exec runuser -u claude -- "$@"
