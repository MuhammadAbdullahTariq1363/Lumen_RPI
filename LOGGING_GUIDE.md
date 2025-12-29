# LUMEN Logging Guide

v1.5.0 - Clean logging strategy

## Logging Levels

### **Console (Mainsail/Fluidd)**
Only when `debug: console` in moonraker.conf:
- ✅ **Errors** - Critical failures that affect LED control
- ✅ **Warnings** - Configuration issues, invalid colors, proxy failures
- ❌ **Debug** - Never sent to console (too spammy)

### **journalctl (System Logs)**
Always logged:
- ✅ **Errors** - All errors
- ✅ **Warnings** - All warnings
- ✅ **Info** - Important state changes (startup, config load, driver creation)
- ✅ **Debug** - Only when `debug: true` or `debug: console` in moonraker.conf

## What Gets Logged

### Startup & Configuration
```
[INFO] Loaded: 3 groups, 7 events
[INFO] Created driver for group 'chamber': proxy
[DEBUG] Cached driver intervals for 3 groups
```

### State Changes (Important Events)
```
[DEBUG] Event: heating
[DEBUG] Applying event: heating to 3 groups
[INFO] ProxyDriver left recovered (was 5 failures)  # Only on recovery
```

### Errors & Warnings
```
[ERROR] Config error: max_brightness must be 0.0-1.0, got 5.0
[WARNING] Group 'chamber': Unknown color 'bluee'. Using white as fallback.
[WARNING] ProxyDriver left failed after 3 retries: Connection refused (consecutive failures: 1)
```

### Debugging (Throttled)
```
[DEBUG] Thermal chamber: source=bed, current=65.2, target=110.0, floor=25  # Only on temp change ≥1°C or every 10s
[DEBUG] Macro detected: G28 → state: homing
[DEBUG] Macro completion detected: homing
```

## What Was Removed (v1.5.0)

❌ **Removed chase effect spam:**
- `Chase 1 (left): 17 LEDs, direction=reverse...` (60 FPS = 60/sec)
- `Multi-chase: total_leds=51, predator_pos=35.4...` (60 FPS)
- `Sent 17 colors to right (direction=standard)` (60 FPS)

These were debug logs that fired **every frame** (60 times per second), causing:
- Console spam (hundreds of lines per second)
- journalctl bloat (fills disk)
- Performance impact (logging overhead)

## Configuring Debug Levels

### Minimal Logging (Production)
```ini
[lumen]
config_path: ~/printer_data/config/lumen.cfg
debug: false  # No debug logs at all
```

### Journal Debug (Troubleshooting)
```ini
[lumen]
debug: true  # Debug to journalctl only, not console
```

### Console Debug (Active Development)
```ini
[lumen]
debug: console  # Debug to both journalctl AND Mainsail console
```

## Viewing Logs

### Mainsail/Fluidd Console
- Click "Console" tab
- Errors/warnings shown in red/yellow (if `debug: console`)

### journalctl (SSH)
```bash
# Follow LUMEN logs in real-time
journalctl -u moonraker -f | grep LUMEN

# Last 100 LUMEN log lines
journalctl -u moonraker -n 100 | grep LUMEN

# LUMEN logs from last hour
journalctl -u moonraker --since "1 hour ago" | grep LUMEN

# Filter only errors
journalctl -u moonraker | grep "LUMEN.*ERROR"
```

## Best Practices

1. **Use `debug: false` in production** - Minimal overhead
2. **Use `debug: console` only when actively troubleshooting** - Verbose
3. **Check `/server/lumen/status` for health info** - No log spam needed
4. **Warnings in status API** - All config warnings exposed via API

## Log Rationale

**Why so few logs?**
- LUMEN runs at **60 FPS** on GPIO drivers
- Every debug log = 60 lines/second = 3600 lines/minute
- This fills disks and drowns important messages

**What should trigger a log?**
- ✅ State change (once per transition)
- ✅ Error/warning (important to know)
- ✅ Recovery from failure (informational)
- ❌ Every animation frame (way too much)
- ❌ Every LED update (performance killer)

**Use the API instead:**
```bash
# Check LUMEN status without logs
curl http://localhost:7125/server/lumen/status | jq

# See active effects, warnings, driver health
curl http://localhost:7125/server/lumen/status | jq '.animation, .warnings, .driver_health'
```

---

**v1.5.0 Changes:**
- Removed 3 verbose chase effect debug logs (180+ lines/second)
- Added warning/error console output when `debug: console`
- Added ProxyDriver health tracking in status API
- All important info available via API, not logs
