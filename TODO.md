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

## ✅ v1.5.0 - Critical Bug Fixes & Performance (January 2026)

### Critical Bug Fixes - COMPLETED ✅
- [x] **GPIO Driver FPS Bottleneck** - Fixed module identity mismatch causing 5s update intervals instead of 60 FPS
  - Removed local imports that created duplicate class objects
  - Added missing GPIODriver, ProxyDriver to top-level imports
  - Added _cache_driver_intervals() call after config reload
  - GPIO strips now update at true 0.0167s intervals (60 FPS target)
  - Achieving 46.87 actual FPS in animation loop
- [x] **State Detection Flip-Flopping** - Fixed heating/printing state transitions
  - Added MIN_PRINT_TEMP = 200°C threshold to distinguish PRINT_START prep from actual printing
  - Fixed heating detector to stay active when ANY heater has target > 0
  - Removed manual print_stats check causing detector conflicts
  - Added has_temp_target check to prevent false "temps ready" during bed-only preheat
  - Smooth state flow: heating → printing → cooldown → idle
- [x] **Log Spam** - Removed "Next updates in" debug log firing every animation frame
- [x] **FPS Counter** - Real-time FPS tracking in /server/lumen/status API
  - Lightweight 30-frame rolling average
  - Shows actual animation loop performance
  - Minimal overhead

### Performance Optimizations - COMPLETED ✅
- [x] **ProxyDriver Batch Updates** - Reduced HTTP overhead by 67%
  - Added /batch_update endpoint to ws281x_proxy.py
  - Animation loop now batches ProxyDriver updates per proxy server
  - Single HTTP request per frame instead of one per LED group
  - HTTP requests: ~84 req/s → ~30 req/s (67% reduction) with 3 groups
  - Scales efficiently when adding more LED groups
  - Single strip.show() call per GPIO pin for better efficiency
- [x] **Performance Metrics API** - Comprehensive monitoring in /server/lumen/status
  - Real-time FPS counter (46.87 FPS achieved)
  - HTTP requests per second tracking (0.02 req/s during printing)
  - Console sends per minute tracking (0.0 sends/min during printing)
  - CPU and memory usage metrics (13.3% CPU, 66.8 MB memory)
  - Thermal debug logging disabled during printing to reduce G-code queue pressure
- [x] **Per-Group Brightness Control** - Fine-grained brightness multipliers
  - Added group_brightness parameter (0.0-1.0) to each [lumen_group] section
  - Removed global max_brightness application from base colors
  - Per-group brightness applied after effect calculation in animation loop
  - Flow: Base Color (1.0) → Effect Brightness (0.0-1.0) → Group Brightness (0.0-1.0) → Final Output
  - Enables different brightness per LED group for different power supplies
  - All example configs updated with group_brightness parameter
  - Deprecated global max_brightness with warning message

### LED Cleanup Bug Fixes - COMPLETED ✅
- [x] **Off Effect LED Cleanup** - Fixed LEDs staying on during sleep transitions
  - Root cause: Multi-group chase coordination continued rendering even after groups switched to "off"
  - Fix 1: Changed off effect to return per-LED colors [(0,0,0)] * led_count
  - Fix 2: Added explicit per-LED clearing in immediate effect application
  - Fix 3: Skip animation loop rendering for "off" effect
  - Fix 4: Added debug logging for LED clearing verification
  - Fix 5: Added timing delays and double-send to prevent race conditions
  - Fix 6: Skip multi-group chase rendering if any chase group has "off" effect
  - Fix 7: Added delayed cleanup task for sleep state (2-second fallback)
  - Fix 8: Block chase group detection entirely during sleep state (ROOT CAUSE FIX)
  - Fixed AttributeError: use state_detector.current_event property instead of get_current_event() method
  - All LEDs now turn off reliably during bored→sleep transitions

## ✅ v1.6.0 - Config Validation Hardening (January 2026)

### Config Validation - COMPLETED ✅
- [x] **ProxyDriver error recovery** - Add retry logic with exponential backoff
  - Added retry logic to batch_update() static method (3 retries, exponential backoff)
  - timeout=1.0 already implemented in v1.5.0
  - Proxy health status already exposed in /server/lumen/status API (v1.5.0)
  - Stop retrying after 10 consecutive failures implemented in v1.5.0
- [x] **Thermal/Progress effect None checks** - Prevent crashes on sensor failures
  - Already implemented in v1.5.0 (thermal.py:138-139, progress.py:54-56)
  - Returns start_color fallback when temp/progress is None
- [x] **Config validation hardening** - Reject invalid configs entirely
  - Brightness validation (0.0-1.0) already in v1.5.0
  - min_sparkle ≤ max_sparkle validation already in v1.5.0
  - Effect/state name validation already in v1.5.0
  - Color name validation added in v1.6.0 - config fails to load on invalid colors
- [x] **Color parsing error visibility** - Show errors in console, not just logs
  - Added _validate_colors_in_mapping() for group effect colors
  - Added _validate_colors_in_effect_settings() for effect parameters
  - Config load fails immediately with clear error messages
  - No more silent fallback to white - immediate feedback on typos

## ✅ v1.6.5 - API Improvements (January 2026)

### API Enhancements - COMPLETED ✅
- [x] **GET /server/lumen/effects** - List all available effects and parameters
  - Comprehensive effect catalog with parameter info, defaults, ranges, descriptions
  - Returns name, description, requires_led_count, requires_state_data, parameters
  - Documents speed, brightness, sparkle, rainbow_spread, chase colors, KITT settings, gradient curves
  - Usage: `curl http://localhost:7125/server/lumen/effects | jq`
- [x] **POST /server/lumen/set_group** - Temporarily override group effect via API
  - Parameters: group (required), effect (required), color (optional), duration (optional)
  - Validates group name, effect name, and color name with helpful error messages
  - Immediately applies override, reverts after duration or on next state change
  - Usage: `curl -X POST "http://localhost:7125/server/lumen/set_group?group=left&effect=pulse&color=red&duration=10"`
- [x] **Macro integration** - Klipper macros for LUMEN control
  - Created examples/lumen_macros.cfg with LUMEN_RELOAD, LUMEN_TEST, LUMEN_SET macros
  - Ready-to-use examples for PRINT_START/PRINT_END integration
  - Convenient LED control from G-code macros

## ✅ v1.7.0 - Debugging Tools (January 2026)

### Test Mode - COMPLETED ✅
- [x] **Effect/state testing mode** - Test effects/states using simple macros
  - LUMEN_TEST_START - Enter test mode
  - LUMEN_TEST_NEXT_STATE - Cycle to next state
  - LUMEN_TEST_PREV_STATE - Cycle to previous state
  - LUMEN_TEST_NEXT_EFFECT - Cycle to next effect
  - LUMEN_TEST_PREV_EFFECT - Cycle to previous effect
  - LUMEN_TEST_STOP - Exit test mode, reload config
  - Six new API endpoints for test mode control
  - Test mode overrides normal state detection
  - Allows rapid cycling through all 14 states and 12 effects
  - Perfect for debugging LED configurations without triggering actual printer states

### Performance Profiling - COMPLETED ✅
- [x] **Performance profiling** - Built-in profiling mode
  - Add profiling_enabled: true to [lumen_settings]
  - Log FPS, CPU %, memory, max frame time, console sends/min, uptime every 60 seconds
  - Automatic profiling loop that starts/stops with animation loop
  - Helps diagnose performance issues without external tools
  - Format: `[PROFILING] FPS: 46.9, CPU: 12.5%, Memory: 68.2 MB, Max frame time: 15.32 ms, Console sends/min: 0.0, Uptime: 125.3 min`

### Unit Testing
- [ ] **Config parsing tests** - Validate all config combinations
- [ ] **State detection tests** - Mock PrinterState, verify events
- [ ] **Effect calculation tests** - Verify each effect's output
- [ ] **Driver tests** - Mock driver responses

### v1.8.0 Tasks Documentation
- [ ] **Color reference with visuals** - GitHub page showing all 50+ colors
- [ ] **Web-based configuration UI** - Visual config editor (research phase)

---

## 🔔 v1.9.1 - WebSocket Notifications (Future Discussion)

### Real-time State Broadcasting
- [ ] **WebSocket notifications** - Broadcast state changes to Mainsail/Fluidd
  - Deferred from v1.6.5 - requires architectural discussion
  - Needs design for efficient state change broadcasting
  - Consider: persistent connections, broadcast management, performance impact
  - To be discussed: why needed, how to implement, integration with existing UIs

---

## 🎯 v1.9.0 - Macro Detection Overhaul
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

### v1.9.9 Electrical Requirements
- [ ] **Document electrical requirements and proper power supply setup**
  - Power supply sizing guidelines for different LED strip lengths
  - Voltage requirements and current calculations
  - Klipper groups vs. Proxy groups power considerations
  - Meanwell PSU recommendations for dedicated supplies
  - Junction block wiring best practices
  - Example: Klipper groups at 0.2-0.4 brightness for voltage control with shared PSU
  - Example: Proxy groups at 1.0 brightness with dedicated Meanwell PSU

---

## 🎮 v2.0.0- Fun Features (Q2 2026)

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



---


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

- **Effect transitions/crossfade** - Smooth color transitions when switching states
  - Add `transition_time: 0.5` to [lumen_settings]
  - Interpolate between old and new colors over N frames
  - Professional polish, reduces jarring changes
- LED strip health monitoring (detect dead LEDs, report via API)

---

**Last Updated:** January 2, 2026
**Current Version:** v1.7.0 (stable)
**Status:** v1.7.0 STABLE - Production tested on Voron Trident | Debugging tools (test mode for state/effect cycling, performance profiling), API improvements (effects listing, group overrides, macro integration), config validation hardening
