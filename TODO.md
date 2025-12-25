# LUMEN Development Roadmap

Active development tasks and future enhancements for LUMEN.

---

## ✅ v1.0.0 Stable Release (December 2025)

### Core Features
- [x] Real-time state detection (idle, heating, printing, cooldown, error, bored, sleep)
- [x] GPIO driver with ws281x-proxy (60fps, bypasses G-code queue)
- [x] Klipper driver (SET_LED for MCU-attached LEDs)
- [x] PWM driver (SET_PIN for non-addressable strips)
- [x] Effects: solid, pulse, heartbeat, disco, thermal, progress
- [x] 50+ named colors (Aurora-compatible)
- [x] Hot reload via `/server/lumen/reload` API
- [x] Config validation with helpful warnings
- [x] Debug logging to journalctl and Mainsail console
- [x] Interactive installer with auto-path detection
- [x] Thread-safe ws281x proxy with proper locking
- [x] Shutdown cleanup handler (turns off LEDs gracefully)
- [x] Motion report subscription for position tracking

### Bug Fixes (December 19-20, 2025)
- [x] Fixed install.sh proxy path (line 342)
- [x] Fixed race condition in ws281x_proxy.py (global _strip_locks_lock)
- [x] Fixed GPIO driver strip expansion (properly recreates PixelStrip)
- [x] Fixed ProxyDriver async init (removed broken code)
- [x] Added color_order validation with warnings
- [x] Verified gpio_fps setting actively used (line 634)
- [x] Added thermal logging throttle (only on temp change ≥1°C or every 10s)
- [x] Added motion_report to initial query (position available immediately)
- [x] Fixed config parser not storing gpio_pin, proxy_host, proxy_port, color_order
- [x] Fixed effect state race condition (apply immediate effects before updating state)
- [x] Fixed debug logging modes (False/True/console now work correctly)
- [x] Enhanced uninstaller to remove moonraker.conf sections automatically
- [x] Enhanced uninstaller to optionally remove ~/lumen directory
- [x] Added helpful debug mode comments to installer

---

## ✅ v1.2.0 - Additional Printer States (December 2025)

### New States to Detect
- [x] **Homing** - G28 in progress
- [x] **Meshing** - BED_MESH_CALIBRATE running
- [x] **Leveling** - QUAD_GANTRY_LEVEL or Z_TILT_ADJUST running
- [x] **Probing** - PROBE_CALIBRATE or similar
- [x] **Paused** - Print paused by user or PAUSE macro
- [x] **Cancelled** - Print cancelled by CANCEL_PRINT macro
- [x] **Filament Change** - Filament load/unload/runout (M600, etc.)

**Implementation Approach:**
- User-configurable macro tracking in `[lumen_settings]`
  ```ini
  macro_homing: G28
  macro_meshing: BED_MESH_CALIBRATE
  macro_leveling: QUAD_GANTRY_LEVEL, Z_TILT_ADJUST
  macro_probing: PROBE_CALIBRATE
  macro_paused: PAUSE
  macro_cancelled: CANCEL_PRINT
  macro_filament: M600, FILAMENT_RUNOUT, LOAD_FILAMENT, UNLOAD_FILAMENT
  ```
- Subscribe to `notify_gcode_response` via Moonraker websocket
- Parse G-code responses for configured macro names
- Set appropriate state when macro detected
- Return to normal state cycle when macro completes

**Benefits:**
- Universal compatibility with any printer's custom macros
- User has full control over which macros trigger which states
- No need to hardcode macro names or maintain compatibility lists
- Simple implementation using existing Moonraker infrastructure

---

## 🎨 v1.1.0 - New Effects (December 2025)

### Completed Effects ✅
- [x] **Rainbow** - Cycling rainbow pattern
  - HSV-based smooth spectrum rotation
  - Configurable spread across LED strip
  - Works with single and multi-LED strips
- [x] **Fire** - Flickering flame simulation
  - Per-LED heat tracking for realistic flicker
  - Orange/red/yellow color spectrum
  - Configurable cooling rate for chaos control
- [x] **Comet** - Moving light with trailing tail
  - Bright head with exponential tail fade
  - Configurable tail length and fade rate
  - Supports forward and reverse direction

### v1.1.5 Completed Effects ✅
- [x] **Chase** - Predator/prey chase with multi-group coordination
  - Single-group mode with dynamic offset variation
  - Multi-group circular array coordination
  - Collision detection with bounce and role swap
  - Proximity acceleration when close
  - Random direction changes and role swaps
  - Respects direction setting per group
- [x] **KITT** - Knight Rider scanner effect
  - Smooth bounce animation with fading tail
  - Optional bed mesh tracking (follows X or Y axis)
  - Configurable eye size and tail length


**Implementation Notes:**
- All effects registered in EFFECT_REGISTRY
- Effect parameters added to EffectState dataclass
- Configuration examples in lumen.cfg.example
- All effects tested via preflight_check.py

---

## ✅ v1.3.0 - Data Sources (December 2025)

### New Temperature Sources
- [x] **Chamber temperature** - Add to thermal effect
  - Subscribe to `temperature_sensor chamber` if available
  - Graceful fallback if not present
  - Thermal effect now supports `temp_source: chamber`

### Filament Sensor Integration
- [x] **Filament runout detection** - Trigger special effect
  - Subscribe to `filament_switch_sensor filament_sensor` events
  - Automatically triggers `on_filament` state when runout detected
  - Works alongside macro-triggered filament states

---

## 🔧 v1.4.0 - Clean Up and Optimize
- [ ] **Cleanup** - Identify and remove - dead and dying code. Ensure proper documentation within code for clear purpose
- [ ] **Update** - Update All Docs with status and intenet. Remove dead and dying information as needed.
- [ ] **Identify areas for optimization** - Identify areas for optimization and an order of importance. Implement as needed

---

## 🔧 v1.5.0 - Quality of Life

### Configuration Enhancements
- [ ] **Group Min/Max brightness** - Allow group based min/max brightness
### API Improvements
- [ ] **GET /server/lumen/effects** - List all available effects and parameters
- [ ] **POST /server/lumen/set_group** - Temporarily override group effect via API
- [ ] **WebSocket notifications** - Broadcast state changes to Mainsail/Fluidd
- [ ] **Macro integration** - LUMEN_SET_RELOAD reload lumen after a .cfg change

### Debugging Tools
- [ ] **Effect preview mode** - Test effects without changing hardware
- [ ] **FPS counter** - Report actual achieved frame rate
- [ ] **Performance profiling** - Identify slow effects or bottlenecks

---

## 🎮 v1.6.0 - Fun Features

### PONG Mode
- [ ] **LED Pong game** - Printer plays during long prints!
  - Use position_x for paddle control
  - Use postion_y for cross "board" postion tracking and "scoring" calculation. Will need to read the printer.cfg for x and y size to determine LED index to display at which coord. Will need some thought to come up with proper method.
  - Ball bounces off "walls" (LED ends)
  - Score tracking via progress bar injection for scoring events and to show winner then end injection and continue progress bar.
  - Winner to be shown at 99% complete
  -

---

## 🐛 Known Issues / Tech Debt

### Performance
- [ ] Optimize disco effect random seed (currently uses time.time())
- [ ] Add frame skip detection for overloaded systems
- [ ] Consider LRU cache for color lookups

### Code Quality
- [ ] Add type stubs for better IDE support
- [ ] Unit tests for state detection logic
- [ ] Integration tests for drivers (with mock hardware)
- [ ] Add mypy/flake8 to CI/CD

### Documentation
- [ ] Video tutorial for installation
- [ ] GIF demonstrations of each effect
- [ ] Troubleshooting flow chart

---

## 🚫 Non-Goals (Won't Implement)

- **RGB color mixing in config** - Use named colors or extend color.py
- **Per-LED config in lumen.cfg** - Use `index_start`/`index_end` groups instead
- **Windows/macOS support** - Raspberry Pi GPIO is Linux-only
- **Standalone mode without Moonraker** - LUMEN is a Moonraker component by design
- **GUI configuration tool** - Editing lumen.cfg is intentionally simple

---

## 📅 Release Cycle

- **Patch releases (v1.0.x)**: Bug fixes only, no new features
- **Minor releases (v1.x.0)**: New features, backward compatible
- **Major releases (v2.0.0+)**: Breaking changes (config format, API changes)

**Current stable:** v1.3.0 (December 2025)
**In development:** v1.4.0 (Clean up and optimize)
**Next planned release:** v1.4.0 (Clean up and optimize) - Q1 2026

---

## 🙏 Contributing

Want to help? Check the roadmap above and:
1. Open an issue to discuss your idea
2. Fork the repo and create a feature branch
3. Submit a PR with clear description and testing notes

See existing code for patterns (async/await, type hints, docstrings).

---

## 📝 Ideas Parking Lot

Random ideas not yet prioritized:

- Adaptive brightness based on time of day
- Sunrise/sunset effect (gradual warm color fade)
- Integration with Home Assistant (publish state via MQTT)
- LED strip health monitoring (detect dead LEDs, report via API)
- Custom user effects via Python plugins
- Multi-zone thermal gradients (bed left/right, extruder zones)
- Print time remaining estimation (via progress effect labels)

---

**Last Updated:** December 24, 2025
**Current Version:** v1.3.0 (stable)
**Status:** v1.3.0 Stable - Production tested on Voron Trident | Adds macro-triggered states (homing, meshing, leveling, probing, paused, cancelled, filament), chamber temperature support, and filament sensor integration
