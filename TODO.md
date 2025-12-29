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

## ✅ v1.4.0 - Clean Up and Optimize (December 2025)

### Performance Optimizations
- [x] **Driver interval caching** - Eliminated 240-300 isinstance() checks per second (60 FPS)
- [x] **State_data pre-building** - Build once per cycle instead of per effect (93% reduction)
- [x] **HSV utility extraction** - Shared hsv_to_rgb() eliminates ~90 lines of duplication
- [x] **Loop attribute caching** - Cache repeated lookups in chase, kitt, fire effects
- [x] **Disco random selection** - Optimized from O(n log n) to O(k) algorithm

### Critical Bug Fixes
- [x] **Disco bounds validation** - Fixed ValueError when min_sparkle > max_sparkle
- [x] **Thermal division by zero** - Added safety check for edge cases

### Code Cleanup
- [x] **Removed unused imports** - Deleted json, os from lumen.py
- [x] **Removed dead telemetry code** - Cleaned up unused tracking variables
- [x] **Removed unused PWMDriver methods** - Deleted set_on() and set_dim()
- [x] **Added error logging** - Improved debugging for silent exception handlers

---

## 🔧 v1.5.0 - Stability & Error Handling (December 2025)

### Critical Bug Fixes
- [ ] **ProxyDriver error recovery** - Add retry logic with exponential backoff
  - Add timeout=1.0 to urllib requests
  - Retry 3 times on network failures
  - Expose proxy health status in /server/lumen/status API
  - Stop retrying after N consecutive failures to prevent log spam
- [ ] **Thermal/Progress effect None checks** - Prevent crashes on sensor failures
  - Check if current_temp/target_temp is None before calculations
  - Check if progress is None before gradient calculations
  - Return safe fallback colors instead of crashing
- [ ] **Config validation hardening** - Reject invalid configs entirely
  - Validate brightness values (0.0-1.0) in _load_config()
  - Validate min_sparkle ≤ max_sparkle for disco effect
  - Validate all effect/state names exist before loading
  - Raise clear errors instead of silent fallbacks
- [ ] **Color parsing error visibility** - Show errors in console, not just logs
  - Return None on parse failures instead of defaulting to white
  - Check for None in caller and add to warnings list
  - Display parse errors in /server/lumen/status API
  - Reject config reload if color parsing fails

### Driver Optimizations
- [ ] **Klipper driver selective updates** - Prevent G-code queue overload
  - Only update GPIO/Proxy drivers at full FPS (60 Hz)
  - Update Klipper drivers at slow rate defined in [lumen_settings]
  - Keep GPIO strips running at gpio_fps during prints
  - Prevents mixed-driver setups from being limited by Klipper queue
  - Note: This is already partially implemented via update_rate settings, but needs separation per driver type in animation loop

### Unit Testing
- [ ] **Config parsing tests** - Validate all config combinations
  - Test valid configs parse correctly
  - Test invalid values are rejected
  - Test inline effect parameters
  - Test color parsing edge cases
- [ ] **State detection tests** - Mock PrinterState, verify events
  - Test priority ordering (error > heating > printing > idle)
  - Test macro state transitions
  - Test timeout behaviors (bored, sleep)
  - Test filament sensor integration
- [ ] **Effect calculation tests** - Verify each effect's output
  - Test solid returns single color
  - Test pulse brightness oscillation
  - Test thermal gradient edge cases (None temps, zero range)
  - Test progress gradient with 0%, 50%, 100%
  - Test disco random selection within bounds
- [ ] **Driver tests** - Mock driver responses
  - Test ProxyDriver retry logic
  - Test KlipperDriver batch commands
  - Test GPIODriver thread safety
  - Test PWMDriver brightness scaling

### Configuration Enhancements
- [ ] **Group Min/Max brightness** - Allow group-based min/max brightness override
- [ ] **Effect presets library** - Ship ready-to-use config presets
  - presets/subtle.cfg - Calm pulse effects, low brightness
  - presets/gaming.cfg - Rainbow, disco, high brightness
  - presets/professional.cfg - Solid colors only
  - presets/voron.cfg - Voron-specific multi-zone setup

### API Improvements
- [ ] **GET /server/lumen/effects** - List all available effects and parameters
- [ ] **POST /server/lumen/set_group** - Temporarily override group effect via API
- [ ] **WebSocket notifications** - Broadcast state changes to Mainsail/Fluidd
- [ ] **Macro integration** - LUMEN_SET_RELOAD reload lumen after a .cfg change

### Debugging Tools
- [ ] **Effect/state testing mode** - Test effects/states using simple macros
  - LUMEN_TEST_START - Enter test mode
  - LUMEN_TEST_NEXT_STATE - Cycle to next state
  - LUMEN_TEST_PREV_STATE - Cycle to previous state
  - LUMEN_TEST_NEXT_EFFECT - Cycle to next effect
  - LUMEN_TEST_PREV_EFFECT - Cycle to previous effect
  - LUMEN_TEST_STOP - Exit test mode, reload config
- [ ] **FPS counter** - Report actual achieved frame rate in status API
- [ ] **Performance profiling** - Built-in profiling mode
  - Add profiling_enabled: true to [lumen_settings]
  - Log FPS, CPU %, max frame time every 60 seconds
  - Helps diagnose performance issues without external tools

### Documentation
- [ ] **Color reference with visuals** - GitHub page showing all 50+ colors
  - Consider adding GIFs of each effect in action
  - Visual reference makes choosing colors/effects easier
- [ ] **Web-based configuration UI** - Visual config editor (research phase)
  - Visit http://printer.local:7125/lumen/config
  - Visual color picker
  - Effect preview animations (canvas-based)
  - Live testing (trigger states manually)
  - Research implementation approach and scope

---

## 🎯 v1.6.0 - Macro Detection Overhaul (Q1 2026)

### Critical Macro Tracking Improvements
- [ ] **Dedicated LUMEN macros for state tracking** - Reliable start/end detection
  - Create LUMEN wrapper macros (similar to Aurora's approach)
  - LUMEN_HOMING_START / LUMEN_HOMING_END
  - LUMEN_MESHING_START / LUMEN_MESHING_END
  - LUMEN_LEVELING_START / LUMEN_LEVELING_END
  - LUMEN_PROBING_START / LUMEN_PROBING_END
  - LUMEN_PAUSED_START / LUMEN_PAUSED_END
  - LUMEN_CANCELLED / LUMEN_FILAMENT_CHANGE
  - Users call these from their existing macros (G28, BED_MESH_CALIBRATE, etc.)
  - Provides explicit state control vs. fragile gcode_response parsing

- [ ] **Hybrid detection system** - Combine macros + gcode_response
  - Prefer LUMEN macro signals when available (explicit, reliable)
  - Fall back to gcode_response parsing if macros not called
  - Best of both worlds: works out-of-box, better with macros

- [ ] **Improved completion detection** - Handle edge cases
  - Detect explicit cancellation ("!! Cancelled" in gcode_response)
  - Track multiple simultaneous macros (rare but possible)
  - Individual timeout tracking per macro type (dict of timestamps)
  - Expose active_macro_state in /server/lumen/status for debugging

- [ ] **Silent macro handling** - Deal with G28 and other quiet macros
  - Research Klipper's silent macro behavior
  - Test detection reliability on G28, G29, etc.
  - Document which macros require LUMEN wrapper macros
  - Provide example macro implementations in docs

---

## 🎮 v1.7.0 - Fun Features (Q2 2026)

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

- **Patch releases (v1.x.y)**: Bug fixes only, no new features
- **Minor releases (v1.x.0)**: New features, backward compatible
- **Major releases (v2.0.0+)**: Breaking changes (config format, API changes)

**Current stable:** v1.4.1 (December 2025)
**In development:** v1.5.0 (Stability & Error Handling)
**Next planned releases:**
- v1.5.0 (Stability & Error Handling) - Q1 2026
- v1.6.0 (Macro Detection Overhaul) - Q1 2026
- v1.7.0 (Fun Features / PONG Mode) - Q2 2026

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

- **Conditional effects** - Complex state-based effect logic
  - Example: `on_printing: if progress < 0.5 then pulse ice else pulse lava`
  - Example: `on_heating: if bed_temp < 60 then thermal bed ice lava else solid lava`
  - Could add interesting dynamic behavior but increases config complexity
- **Effect transitions/crossfade** - Smooth color transitions when switching states
  - Add `transition_time: 0.5` to [lumen_settings]
  - Interpolate between old and new colors over N frames
  - Professional polish, reduces jarring changes
- Adaptive brightness based on time of day
- Sunrise/sunset effect (gradual warm color fade)
- Integration with Home Assistant (publish state via MQTT)
- LED strip health monitoring (detect dead LEDs, report via API)
- Custom user effects via Python plugins (effect marketplace)
- Multi-zone thermal gradients (bed left/right, extruder zones)
- Print time remaining estimation (via progress effect labels)
- Hardware PWM support for Pi 5 (rpi_hardware_pwm library, 120+ FPS)

---

**Last Updated:** December 28, 2025
**Current Version:** v1.4.1 (stable)
**Next Release:** v1.5.0 - Stability & Error Handling (focusing on testing, validation, and hardening before new features)
**Status:** v1.4.1 Stable - Production tested on Voron Trident | Fixed critical macro tracking bugs (infinite loop console spam, Klipper driver timeout spam during macros), added 30-second macro timeout, selective driver updates during macro states
