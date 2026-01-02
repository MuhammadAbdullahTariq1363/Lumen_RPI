# Changelog

All notable changes to LUMEN will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.5.0] - 2026-01-01

### 🐛 Critical Bug Fixes

#### GPIO Driver FPS Bottleneck (Bug #1)
- **Root cause**: Module identity mismatch caused `isinstance()` checks to fail, forcing GPIO/Proxy drivers to use slow Klipper intervals (5s during printing instead of 0.0167s at 60 FPS)
- **Fix**: Removed local imports in `_cache_driver_intervals()` and `_handle_status()` that created duplicate class objects (lumen.py:586-587, 1356)
- **Fix**: Added missing `GPIODriver, ProxyDriver` to top-level imports (lumen.py:30)
- **Fix**: Call `_cache_driver_intervals()` after config reload to rebuild interval cache (lumen.py:1411)
- **Impact**: GPIO strips now update at true 60 FPS (0.0167s intervals), achieving 31+ actual FPS in animation loop
- **Diagnostic**: Added driver interval logging showing "GPIO/Proxy interval=0.0167s (FPS=60)" vs "Klipper/PWM printing=5.0s, idle=0.1s"

#### State Detection Flip-Flopping (Bug #2)
- **Root cause**: Multiple logic errors in heating/printing state detectors caused incorrect transitions
- **Fix**: Added `MIN_PRINT_TEMP = 200.0°C` threshold to distinguish PRINT_START prep (cartographer touch at 150°C) from actual printing (printing.py:28-29, 81-83)
- **Fix**: Changed heating detector to stay active when ANY heater has target > 0, removing temperature proximity checks (heating.py:35-103)
- **Fix**: Removed manual `print_stats` check from heating detector that caused both detectors to return False → idle (heating.py removed lines checking print_stats)
- **Fix**: Added `has_temp_target` check to prevent false "temps ready" during bed-only preheat (printing.py:73-76)
- **Impact**: Smooth state transitions during full print cycle: heating (bed preheat) → heating (extruder 150°C) → heating (probing/meshing) → heating (final heatup) → printing (when extruder >200°C and at target) → cooldown → idle

#### Log Spam
- **Fix**: Removed "Next updates in" debug log that fired every animation frame during printing (lumen.py:1321)
- **Impact**: Eliminated console spam, cleaner journalctl logs

### ✨ New Features

#### Real-time FPS Counter
- **Added**: Lightweight FPS tracking using 30-frame rolling average (lumen.py:109-110, 1162-1164)
- **Added**: `_get_current_fps()` helper method calculates actual animation loop performance (lumen.py:1331-1347)
- **Added**: FPS displayed in `/server/lumen/status` API endpoint under `animation.fps` (lumen.py:1393)
- **Added**: `gpio_fps` config value to status endpoint (lumen.py:1388)
- **Usage**: `curl -s http://localhost:7125/server/lumen/status | python3 -m json.tool`
- **Overhead**: Minimal - just appends timestamp per frame, negligible performance impact

### ⚡ Performance Optimizations

#### ProxyDriver Batch Updates
- **Added**: `/batch_update` endpoint to ws281x_proxy.py accepts multiple LED operations in single HTTP request (ws281x_proxy.py:314-389)
- **Added**: `ProxyDriver.batch_update()` static method for sending batched requests (drivers.py:436-485)
- **Modified**: Animation loop now collects ProxyDriver updates and sends in batches per proxy server (lumen.py:1215, 1313-1372)
- **Impact**: Reduces HTTP overhead from ~84 req/s → ~30 req/s (67% reduction) with 3 ProxyDriver groups
- **Scalability**: Adding more LED groups no longer increases HTTP requests proportionally
- **Efficiency**: Single `strip.show()` call per GPIO pin instead of per LED group
- **Future-proof**: Batching architecture supports multiple proxy servers simultaneously

#### Performance Metrics API
- **Added**: Console sends per minute tracking in status API (lumen.py:113-114, 1389)
- **Added**: CPU and memory usage metrics in status API (lumen.py:1463-1528, 1521-1522)
  - `cpu_percent`: Average Moonraker CPU usage since process started
  - `memory_mb`: Moonraker RSS memory usage in megabytes
  - Uses /proc filesystem for lightweight, accurate measurements
- **Added**: Debug logging throttle for thermal effect during printing - disabled to reduce G-code queue usage (lumen.py:1284-1289)
- **Impact**: Eliminated 12 RESPOND commands/minute during printing, reducing Klipper queue pressure

#### Per-Group Brightness Control
- **Added**: `group_brightness` parameter (0.0-1.0) to each `[lumen_group]` section (lumen.py:422-425, 439)
- **Removed**: Global `max_brightness` application from base colors (lumen.py:851-854, 920-921)
- **Added**: Per-group brightness multiplier applied after effect calculation in animation loop (lumen.py:1321-1329)
- **Flow**: Base Color (1.0) → Effect Brightness (0.0-1.0) → Group Brightness (0.0-1.0) → Final Color
- **Deprecated**: `max_brightness` in `[lumen_settings]` - now shows warning to use `group_brightness` per group (lumen.py:380-389)
- **Impact**:
  - Fixed double-dimming bug where global × effect brightness = much dimmer than expected
  - Enables fine-grained brightness control per LED group for different power supplies
  - Klipper-connected groups can use lower brightness for voltage demands
  - Proxy-connected groups can use full brightness with dedicated power supplies
- **Updated**: All example configs (ender3_simple.cfg, voron_24.cfg, voron_trident.cfg) with `group_brightness` parameter

#### Off Effect LED Cleanup Bug
- **Root cause**: Multi-group chase coordination continued rendering even after groups switched to "off" effect, overwriting clear commands
- **Fix 1**: Changed off effect to return per-LED colors `[(0,0,0)] * led_count` (off.py:34)
- **Fix 2**: Added explicit per-LED clearing in immediate effect application using `set_leds()` (lumen.py:931-942)
- **Fix 3**: Skip animation loop rendering for "off" effect to prevent race condition (lumen.py:1271-1273)
- **Fix 4**: Added debug logging to verify LED clearing during state transitions (lumen.py:934, 938, 942)
- **Fix 5**: Added timing delays and double-send to prevent animation loop race conditions (lumen.py:931-956)
  - Wait 50ms before sending first clear command to let animation loop complete
  - Send second clear command after 50ms delay to ensure it takes effect
  - Prevents race condition where animation loop sends updates after immediate clear
- **Fix 6**: Skip multi-group chase rendering if any chase group has "off" effect (lumen.py:1251-1268)
  - Multi-group chase coordination was continuing to render even after state changed to "off"
  - Now checks all chase groups for "off" effect and skips chase rendering entirely
  - Prevents chase effect from overwriting off commands during bored→sleep transition
- **Fix 7**: Added delayed cleanup task for sleep state (lumen.py:1020-1047, 833-836)
  - Waits 2 seconds after sleep event, then sends final off commands to all groups
  - Ensures LEDs turn off even if there are persistent issues at driver/hardware level
  - Logs cleanup actions for debugging
- **Impact**: Fixed bug where some LEDs stayed on during bored→sleep transition after multi-LED effects (disco, chase, etc.)

### Changed
- Version bumped from v1.4.1 to v1.5.0

---

## [1.4.1] - 2025-12-25

### 🐛 Critical Bug Fixes - Macro Tracking

#### Infinite Loop Console Spam
- **Root cause**: LUMEN console messages containing macro names (e.g., "BED_MESH_CALIBRATE") triggered infinite detection loops
- **Fix**: Added filter to ignore G-code responses starting with "LUMEN" or "// LUMEN" (lumen.py:603-605)
- **Impact**: Prevented system lockups during bed meshing and other macros

#### Malformed G-code Debug Messages
- **Root cause**: Long debug messages with probe results caused truncated RESPOND commands
- **Fix**: Added filter to skip probe result messages (lumen.py:607-610)
- **Impact**: Eliminated "Malformed command" errors in Klipper logs

#### Klipper Driver Timeout Spam
- **Root cause**: Klipper's G-code queue blocks during macro execution, causing SET_LED commands to timeout every 2 seconds
- **Fix**: Skip Klipper driver updates when macro state is active, allowing only GPIO/Proxy drivers to update (lumen.py:956-959, 1071-1075)
- **Impact**: Eliminated timeout spam in logs, LEDs now respond correctly to macro states on GPIO-attached strips

### ✨ New Features
- **Macro completion detection**: Automatically detects macro completion messages (e.g., "// Mesh Bed Leveling Complete") and returns to normal state cycle (lumen.py:612-636)
- **Macro timeout**: 120-second safety timeout prevents stuck macro states if completion message not detected (lumen.py:584-591)

### Changed
- Version bumped from v1.4.0 to v1.4.1

---

## [1.4.0] - 2025-12-25

### ⚡ Performance Optimizations

#### Hot Path Improvements
- **Driver interval caching**: Eliminated 240-300 `isinstance()` checks per second at 60 FPS by pre-caching driver intervals during initialization
- **State_data pre-building**: Build printer state data once per animation cycle instead of rebuilding for each effect (93% reduction in dictionary operations)
- **Loop attribute caching**: Cache repeated attribute lookups in chase, kitt, and fire effects before entering render loops
- **Disco random selection**: Optimized LED selection from O(n log n) sort-based approach to O(k) `random.sample()` algorithm

#### Code Deduplication
- **HSV utility extraction**: Created shared `hsv_to_rgb()` function in `colors.py`, eliminating ~90 lines of duplicated HSV→RGB conversion code across rainbow, fire, and disco effects

### 🐛 Critical Bug Fixes
- **Disco bounds validation**: Fixed `ValueError` crash when `min_sparkle > max_sparkle` by ensuring min ≤ max before calling `random.randint()`
- **Thermal division by zero**: Added safety check to prevent division by zero when `temp_range ≤ 0` in edge cases

### 🔧 Code Cleanup
- **Removed unused imports**: Deleted unused `json` and `os` imports from `lumen.py`
- **Removed dead telemetry code**: Cleaned up unused tracking variables from early development
- **Removed unused PWMDriver methods**: Deleted `set_on()` and `set_dim()` methods (only `set_brightness()` and `set_off()` are used)
- **Added error logging**: Improved debugging by logging exceptions in previously silent exception handlers

### Changed
- Version bumped from v1.3.0 to v1.4.0

---

## [1.3.0] - 2025-12-24

### ✨ New Features

#### Temperature Sources
- **Chamber temperature support**: Added `temp_source: chamber` option for thermal effect
  - Subscribes to `temperature_sensor chamber_temp` if available in Klipper config
  - Graceful fallback if chamber sensor not present
  - Status API now includes `chamber_temp` and `chamber_target` fields

#### Filament Sensor Integration
- **Automatic filament runout detection**: Subscribes to `filament_switch_sensor filament_sensor` events
  - Automatically triggers `on_filament` state when runout detected (`filament_detected: false`)
  - Works alongside existing macro-triggered filament states from v1.2.0
  - Status API includes `filament_detected` field (true/false/null if no sensor)

### Fixed
- **Config validator**: Added v1.2.0 states (homing, meshing, leveling, probing, paused, cancelled, filament) to valid_events set
- **Chamber sensor naming**: Updated code to use `chamber_temp` instead of generic `chamber` to match common Klipper conventions

---

## [1.2.0] - 2025-12-23

### ✨ New Printer States

Added 7 new macro-triggered states with user-configurable tracking:

- **Homing**: G28 in progress
- **Meshing**: BED_MESH_CALIBRATE running
- **Leveling**: QUAD_GANTRY_LEVEL or Z_TILT_ADJUST running
- **Probing**: PROBE_CALIBRATE or similar
- **Paused**: Print paused by user or PAUSE macro
- **Cancelled**: Print cancelled by CANCEL_PRINT macro
- **Filament Change**: Filament load/unload/runout (M600, etc.)

#### Configuration
New `[lumen_settings]` options for macro tracking:
```ini
macro_homing: G28
macro_meshing: BED_MESH_CALIBRATE
macro_leveling: QUAD_GANTRY_LEVEL, Z_TILT_ADJUST
macro_probing: PROBE_CALIBRATE
macro_paused: PAUSE
macro_cancelled: CANCEL_PRINT
macro_filament: M600, FILAMENT_RUNOUT, LOAD_FILAMENT, UNLOAD_FILAMENT
```

New `on_*` effect options for LED groups:
- `on_homing`, `on_meshing`, `on_leveling`, `on_probing`
- `on_paused`, `on_cancelled`, `on_filament`

#### Implementation
- Subscribes to `notify_gcode_response` via Moonraker WebSocket
- Parses G-code responses for user-configured macro names
- Universal compatibility with any printer's custom macros
- Returns to normal state cycle when macro completes

---

## [1.1.5] - 2025-12-22

### ✨ New Effects

#### Chase Effect
Multi-mode predator/prey chase animation:
- **Single-group mode**: Two colored segments chase each other with dynamic offset variation
- **Multi-group circular array mode**: Groups coordinate as a ring with collision detection, role swapping, and proximity acceleration
- Configurable parameters: `chase_size`, `chase_color_1`, `chase_color_2`, `chase_offset_base`, `chase_offset_variation`, `chase_proximity_threshold`, `chase_accel_factor`, `chase_role_swap_interval`, `chase_collision_pause`

#### KITT Effect
Knight Rider-style scanner bounce:
- Smooth back-and-forth animation with bright center "eye"
- Configurable fading tail on both sides
- Optional bed mesh tracking: follows X or Y axis position during moves
- Parameters: `speed`, `base_color`, `kitt_eye_size`, `kitt_tail_length`, `kitt_tracking_axis`

---

## [1.1.0] - 2025-12-22

### ✨ New Effects

#### Rainbow Effect
- Smooth cycling through entire color spectrum using HSV color space
- Configurable spread across LED strip (`rainbow_spread: 0.0-1.0`)
- Works with single and multi-LED configurations
- Parameters: `speed`, `rainbow_spread`, `max_brightness`

#### Fire Effect
- Realistic flickering flame simulation with per-LED heat tracking
- Orange/red/yellow color spectrum (HSV-based)
- Configurable cooling rate for chaos control
- Parameters: `speed`, `min_brightness`, `max_brightness`, `fire_cooling`

#### Comet Effect
- Moving light with exponential trailing tail
- Bright head with configurable fade rate
- Supports forward and reverse direction
- Parameters: `speed`, `max_brightness`, `comet_tail_length`, `comet_fade_rate`

---

## [1.0.0] - 2024-12-21

### 🎉 First Stable Release

Production-ready LED control for Klipper printers. Tested on Voron Trident with full state cycle validation (fresh install → heating → printing → cooldown → idle → bored → sleep → rewake cycle).

**Comprehensive code review completed** - All critical, high, and medium priority issues fixed for release.

### Added

#### Core Features
- **Modular Architecture**: Plugin-based effect and state systems with registry pattern
- Real-time state detection for 7 printer states: idle, heating, printing, cooldown, error, bored, sleep
- GPIO driver with ws281x-proxy (60fps smooth animations, bypasses G-code queue)
- Klipper driver (SET_LED for MCU-attached LEDs)
- PWM driver (SET_PIN for non-addressable LED strips)
- 7 LED effects: solid, pulse, heartbeat, disco, thermal gradient, print progress bar, off
- 50+ named colors (Aurora-compatible palette)
- Hot reload via `/server/lumen/reload` API endpoint
- Config validation with helpful warnings
- Debug logging to journalctl and Mainsail console
- Interactive installer with automatic path detection
- Thread-safe ws281x proxy with proper locking
- Shutdown cleanup handler (gracefully turns off LEDs on exit)
- Motion report subscription for immediate position tracking
- **Task Exception Handling**: Comprehensive error handling for background tasks
- **Performance Optimizations**: Effect instance caching, animation loop improvements

#### Installation & Maintenance
- Automated installer (`install.sh`) with interactive prompts
- Automated uninstaller (`uninstall.sh`) with complete cleanup
- Automatic moonraker.conf section management (install/uninstall)
- Debug mode comments in installer for user guidance

### Fixed

#### Critical Bugs - v1.0 Final Release (December 21, 2024)
- **Memory leak on config reload**: Effect instance cache and thermal log cache now cleared properly
- **Silent task failures**: Background tasks now have exception handlers, errors logged instead of ignored
- **Animation loop race condition**: Properly cancels and awaits old tasks before starting new ones
- **Effect cache corruption**: Per-group effect instance caching prevents state bleeding between groups
- **Bored/Sleep state flapping**: States now persist correctly, no more rapid idle↔bored transitions

#### Critical Bugs - Pre-release (December 19-20, 2024)
- **Config parser bug**: Fixed missing gpio_pin, proxy_host, proxy_port, color_order storage in LED group config
- **Effect state race condition**: Apply immediate effects before updating state to prevent animation loop conflicts
- **Install script path**: Fixed ws281x-proxy path reference (was pointing to outdated location)
- **Race condition in ws281x_proxy.py**: Added global `_strip_locks_lock` for thread-safe lock initialization

#### Driver Improvements
- **GPIODriver thread safety**: Global state protected with per-pin locks
- GPIO driver now properly handles strip expansion (recreates PixelStrip with existing LED states)
- **ProxyDriver connection failures**: Now logged with warnings for debugging
- ProxyDriver async initialization cleaned up (removed broken code)
- KlipperDriver INDEX loop logic verified and documented

#### State Detection Improvements
- **StateDetector listener exceptions**: Now logged instead of silently swallowed
- Bored and sleep states check actual printer state (no heaters, no prints)
- Once entered, states persist correctly until conditions change

#### Logging & Debugging
- Debug logging now properly respects False/True/console modes
- Thermal effect logging throttled (only logs on temp change ≥1°C or every 10s)
- Added color_order validation with helpful warnings
- Task exception handler logs background task failures

#### Performance & Stability
- **Animation loop interval clamping**: Minimum 1ms interval prevents busy-looping
- **Effect instance caching**: Per-group caching eliminates object creation on every frame
- **Smooth 60fps animations**: Achieved on GPIO driver after caching fix

### Documentation
- Comprehensive README.md with installation, configuration, and troubleshooting
- TODO.md roadmap with future feature planning
- Example configuration in `config/lumen.cfg.example`
- GPIO 19 audio conflict troubleshooting documented
- Production status badges and testing notes

---

## Release Notes

### v1.0.0 - What's Working

**Tested Hardware:**
- Voron Trident with Raspberry Pi 4
- WS2812B LED strips on GPIO 21
- Full state cycle validation complete

**Performance:**
- 60fps smooth animations on GPIO driver
- <1% CPU usage on Raspberry Pi 4
- ~50MB memory footprint

**Known Limitations:**
- Klipper driver slower during prints (G-code queue bottleneck) - expected behavior
- GPIO 19 conflicts with audio on Raspberry Pi (use GPIO 18 instead)


---

## Previous Versions

This is the first stable release. Pre-release development history available in commit logs.

---

**Legend:**
- 🎉 Major milestone
- ✨ New feature
- 🐛 Bug fix
- ⚡ Performance improvement
- 📝 Documentation
- 🔧 Maintenance

[1.5.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.5.0
[1.4.1]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.4.1
[1.4.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.4.0
[1.3.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.3.0
[1.2.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.2.0
[1.1.5]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.1.5
[1.1.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.1.0
[1.0.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.0.0
