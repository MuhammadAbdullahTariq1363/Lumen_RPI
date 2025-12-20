---
name: Bug Report
about: Report a bug or issue with LUMEN
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description

**Clear and concise description of the bug:**


## Expected Behavior

**What you expected to happen:**


## Actual Behavior

**What actually happened:**


## Steps to Reproduce

1.
2.
3.
4.

## Environment

**Hardware:**
- Printer: [e.g., Voron 2.4, Ender 3, etc.]
- Raspberry Pi Model: [e.g., Pi 4 Model B, Pi Zero 2W]
- LED Hardware: [e.g., WS2812B strip, 60 LEDs, GPIO 18]
- Power Supply: [e.g., 5V 10A dedicated supply]

**Software:**
- LUMEN Version: [e.g., v1.0.0 - run `git describe --tags` in ~/lumen]
- Klipper Version: [from Mainsail/Fluidd UI]
- Moonraker Version: [from Mainsail/Fluidd UI]
- OS: [e.g., Raspbian Bullseye, DietPi]

**Configuration:**
- Driver Type: [proxy/klipper/pwm]
- Number of LED Groups: [e.g., 2]
- Debug Mode: [False/True/console]

## Logs

**Moonraker logs (LUMEN component):**
```
Paste output from: sudo journalctl -u moonraker | grep LUMEN | tail -100
```

**ws281x-proxy logs (if using GPIO driver):**
```
Paste output from: sudo journalctl -u ws281x-proxy | tail -50
```

**LUMEN status:**
```
Paste output from: curl http://localhost:7125/server/lumen/status | jq
```

## Configuration File

**lumen.cfg (redact sensitive info):**
```ini
Paste your ~/printer_data/config/lumen.cfg here
```

## Additional Context

**Screenshots/Videos:**
[If applicable, attach screenshots or videos showing the issue]

**Related Issues:**
[Link to related issues if any]

**Workarounds Tried:**
[What have you already tried to fix this?]

## Checklist

- [ ] I have checked existing issues for duplicates
- [ ] I have included all requested information above
- [ ] I have tested with debug mode enabled (`debug: console`)
- [ ] I have verified ws281x-proxy service is running (if using GPIO driver)
- [ ] I have tried hot-reloading config (`curl -X POST http://localhost:7125/server/lumen/reload`)
