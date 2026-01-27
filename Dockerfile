FROM ubuntu:24.04

# Avoid interactive prompts during package install
ENV DEBIAN_FRONTEND=noninteractive

# ============================================================
# System packages
# ============================================================
RUN apt-get update && apt-get install -y \
    # Core utilities
    curl \
    wget \
    git \
    unzip \
    jq \
    less \
    vim \
    # Network & firewall (for entrypoint sandbox)
    iptables \
    iproute2 \
    dnsutils \
    libcap2-bin \
    # Audio (PulseAudio client + PortAudio for voice mode)
    pulseaudio-utils \
    libpulse0 \
    libpulse-dev \
    alsa-utils \
    libasound2t64 \
    libasound2-dev \
    libasound2-plugins \
    portaudio19-dev \
    libportaudio2 \
    ffmpeg \
    # Build tools
    build-essential \
    pkg-config \
    ca-certificates \
    gnupg \
    # Python
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Node.js 22
# ============================================================
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# GitHub CLI
# ============================================================
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# uv (Python package manager)
# ============================================================
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && mv /root/.local/bin/uvx /usr/local/bin/uvx

# ============================================================
# Claude Code (native installer)
# ============================================================
RUN curl -fsSL https://claude.ai/install.sh | bash \
    && cp -L /root/.local/bin/claude /usr/local/bin/claude \
    && rm -rf /root/.local/share/claude /root/.local/bin/claude

# ============================================================
# VoiceMode (voice-mode Python package)
# ============================================================
ENV UV_TOOL_DIR=/opt/uv-tools
ENV UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install voice-mode

# Point voice mode at host services (Whisper STT + Kokoro TTS running on Mac with Metal GPU)
ENV VOICEMODE_STT_BASE_URLS=http://host.docker.internal:2022/v1
ENV VOICEMODE_TTS_BASE_URLS=http://host.docker.internal:8880/v1

# ============================================================
# User setup
# ============================================================
RUN useradd --create-home --shell /bin/bash claude \
    && usermod -aG audio claude \
    && mkdir -p /home/claude/.local/bin \
    && chown -R claude:claude /home/claude/.local
ENV PATH="/home/claude/.local/bin:$PATH"

# Suppress PulseAudio shared memory warnings (not needed over TCP)
RUN mkdir -p /home/claude/.config/pulse \
    && echo "enable-shm = false" > /home/claude/.config/pulse/client.conf \
    && chown -R claude:claude /home/claude/.config

# ============================================================
# Entrypoint (firewall + capability drop)
# ============================================================
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Working directory for the sandboxed session
RUN mkdir -p /workspace && chown claude:claude /workspace
WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["claude", "--dangerously-skip-permissions"]
