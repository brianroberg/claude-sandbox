#!/bin/bash
# ============================================================
# Verify that the sandbox network isolation is working.
# Run this INSIDE the container to confirm firewall rules.
# ============================================================

echo "=== Sandbox Network Isolation Test ==="
echo ""

PASS=0
FAIL=0

# Test 1: Public internet access
echo -n "Public internet (ifconfig.me)... "
if curl -s --max-time 5 https://ifconfig.me >/dev/null 2>&1; then
    echo "PASS (allowed)"
    PASS=$((PASS + 1))
else
    echo "FAIL (should be allowed)"
    FAIL=$((FAIL + 1))
fi

# Test 2: PulseAudio on host
echo -n "PulseAudio (host:4713)... "
if timeout 3 bash -c 'echo > /dev/tcp/host.docker.internal/4713' 2>/dev/null; then
    echo "PASS (allowed)"
    PASS=$((PASS + 1))
else
    echo "SKIP (PulseAudio may not be running)"
fi

# Test 3: Other host port should be blocked
echo -n "Host port 80 (should block)... "
if timeout 3 bash -c 'echo > /dev/tcp/host.docker.internal/80' 2>/dev/null; then
    echo "FAIL (should be blocked)"
    FAIL=$((FAIL + 1))
else
    echo "PASS (blocked)"
    PASS=$((PASS + 1))
fi

# Test 4: LAN access should be blocked (common router IPs)
for ip in 192.168.1.1 192.168.0.1 10.0.0.1; do
    echo -n "LAN $ip:80 (should block)... "
    if timeout 3 bash -c "echo > /dev/tcp/$ip/80" 2>/dev/null; then
        echo "FAIL (should be blocked)"
        FAIL=$((FAIL + 1))
    else
        echo "PASS (blocked)"
        PASS=$((PASS + 1))
    fi
done

# Test 5: DNS resolution should work
echo -n "DNS resolution (google.com)... "
if getent hosts google.com >/dev/null 2>&1; then
    echo "PASS (working)"
    PASS=$((PASS + 1))
else
    echo "FAIL (should work)"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"

if [ $FAIL -gt 0 ]; then
    echo "WARNING: Some isolation tests failed!"
    exit 1
else
    echo "All tests passed. Sandbox is properly isolated."
fi
