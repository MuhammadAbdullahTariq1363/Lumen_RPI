# LUMEN Example Configurations

Pre-built configurations for popular 3D printers. Copy the appropriate file to `~/printer_data/config/lumen.cfg` and customize for your setup.

---

## 📁 Available Examples

### [voron_trident.cfg](voron_trident.cfg)
**Tested hardware - Production validated ✅**

- **Printer:** Voron Trident 300mm
- **Raspberry Pi:** Pi 4 Model B
- **LEDs:** 60x WS2812B on GPIO 21
- **Features:**
  - Chamber lighting via GPIO (60fps smooth)
  - Optional toolhead LEDs (commented out)
  - Thermal effect showing bed heating
  - Progress bar during prints
- **Test Results:** Full state cycle validated, <1% CPU usage

**Use this if you have:**
- Voron Trident (any size)
- GPIO-connected chamber LED strip
- Want smooth 60fps animations

---

### [voron_24.cfg](voron_24.cfg)
**Common V2.4 setup**

- **Printer:** Voron 2.4 (any size)
- **LEDs:**
  - Chamber strip on GPIO 18
  - Stealthburner toolhead (logo + nozzle)
- **Features:**
  - Chamber thermal effect (shows chamber temp)
  - Logo LED: Status indicator
  - Nozzle LEDs: Work lights
- **Notes:** Optimized for enclosed printing

**Use this if you have:**
- Voron 2.4
- Both chamber and toolhead LEDs
- Chamber temperature sensor

---

### [ender3_simple.cfg](ender3_simple.cfg)
**Minimal budget-friendly setup**

- **Printer:** Ender 3 / budget printers
- **LEDs:** Single strip on GPIO 18
- **Features:**
  - Simple solid color effects
  - Basic state indication
  - Low CPU usage (works on Pi Zero 2W)
- **Cost:** ~$25 for LED strip + PSU

**Use this if you have:**
- Budget printer (Ender 3, CR-10, etc.)
- Single LED strip
- Want simplest possible setup

---

## 🚀 How to Use

1. **Choose your config:**
   ```bash
   # Example: Using Voron Trident config
   cp ~/lumen/examples/voron_trident.cfg ~/printer_data/config/lumen.cfg
   ```

2. **Customize for your hardware:**
   - Edit LED counts (`index_start`, `index_end`)
   - Adjust GPIO pins if different
   - Change brightness if needed
   - Modify effects to your taste

3. **Restart Moonraker:**
   ```bash
   sudo systemctl restart moonraker
   ```

4. **Verify it works:**
   ```bash
   curl http://localhost:7125/server/lumen/status | jq
   ```

---

## ⚙️ Common Customizations

### LED Count
```ini
index_start: 1
index_end: 60    # Change this to your strip length
```

### Brightness
```ini
[lumen_settings]
max_brightness: 0.4    # 0.1 (dim) to 1.0 (full)
```

### GPIO Pin
```ini
gpio_pin: 18    # Options: 12, 13, 18, 19, 21
```

**Recommended:** GPIO 18 (no conflicts)
**Tested:** GPIO 21 (works great, tested on Trident)
**Avoid:** GPIO 19 (conflicts with audio)

### Color Order
```ini
color_order: GRB    # Try: GRB, RGB, BRG if colors wrong
```

### Effects Per State
```ini
on_idle: solid white              # Static color
on_heating: thermal bed ice lava  # Temperature gradient
on_printing: progress steel matrix  # Print progress bar
on_cooldown: pulse ice            # Breathing effect
on_error: heartbeat red           # Double-pulse
on_bored: disco                   # Party mode!
on_sleep: off                     # LEDs off
```

---

## 🔧 Mixing Drivers

You can combine multiple drivers in one config:

```ini
# Fast chamber effects (GPIO)
[lumen_group chamber]
driver: proxy
gpio_pin: 18
# ... smooth 60fps animations

# Toolhead status (Klipper)
[lumen_group toolhead]
driver: klipper
neopixel: sb_leds
# ... works with MCU LEDs

# Case lights (PWM)
[lumen_group caselight]
driver: pwm
pin_name: caselight_pwm
# ... brightness-only control
```

---

## 📖 Full Documentation

- [Main README](../README.md) - Complete feature documentation
- [lumen.cfg.example](../config/lumen.cfg.example) - All available options
- [CHANGELOG](../CHANGELOG.md) - Release history
- [CONTRIBUTING](../CONTRIBUTING.md) - How to contribute

---

## 💡 Tips

### Testing Your Config

```bash
# Check if LUMEN loaded
curl http://localhost:7125/server/lumen/status

# List available colors
curl http://localhost:7125/server/lumen/colors

# Test a specific state
curl -X POST "http://localhost:7125/server/lumen/test_event?event=heating"

# Hot reload after config changes
curl -X POST "http://localhost:7125/server/lumen/reload"
```

### Troubleshooting

```bash
# Check LUMEN logs
sudo journalctl -u moonraker | grep LUMEN | tail -100

# Check GPIO proxy (if using proxy driver)
sudo systemctl status ws281x-proxy

# Test proxy directly
curl http://127.0.0.1:3769/status
```

### Enable Debug Logging

Edit `~/printer_data/config/moonraker.conf`:

```ini
[lumen]
config_path: ~/printer_data/config/lumen.cfg
debug: console    # Logs to journalctl + Mainsail console
```

---

## 🎨 Effect Reference

| Effect | Description | Example |
|--------|-------------|---------|
| `solid <color>` | Static color | `solid white` |
| `pulse <color>` | Breathing animation | `pulse cobalt` |
| `heartbeat <color>` | Double-pulse | `heartbeat red` |
| `disco` | Random party colors | `disco` |
| `thermal <src> <c1> <c2> <curve>` | Temp gradient | `thermal bed ice lava 2.0` |
| `progress <c1> <c2> <curve>` | Print progress | `progress steel matrix 1.5` |
| `off` | LEDs off | `off` |

---

## 🙋 Need Help?

- **Issue Tracker:** [GitHub Issues](https://github.com/MakesBadDecisions/Lumen_RPI/issues)
- **Discussions:** [GitHub Discussions](https://github.com/MakesBadDecisions/Lumen_RPI/discussions)
- **Bug Reports:** Use our [bug report template](../.github/ISSUE_TEMPLATE/bug_report.md)

---

**Have a config for another printer? [Contribute it!](../CONTRIBUTING.md)**
