"""
LUMEN - Moonraker Component

The conductor - imports from lumen_lib and orchestrates LED effects.

Installation:
    ln -sf ~/lumen/moonraker/components/lumen.py ~/moonraker/moonraker/components/
    ln -sf ~/lumen/moonraker/components/lumen_lib ~/moonraker/moonraker/components/
"""

from __future__ import annotations

__version__ = "1.7.0"

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

# Add our directory to path so we can import lumen_lib
_component_dir = Path(__file__).parent
if str(_component_dir) not in sys.path:
    sys.path.insert(0, str(_component_dir))

from lumen_lib import (
    RGB, get_color, list_colors,
    EffectState,
    LEDDriver, KlipperDriver, PWMDriver, GPIODriver, ProxyDriver, create_driver,
    PrinterState, PrinterEvent, StateDetector,
)
from lumen_lib.effects import EFFECT_REGISTRY

if TYPE_CHECKING:
    from confighelper import ConfigHelper
    from websockets import WebRequest

_logger = logging.getLogger(__name__)


class Lumen:
    """
    LUMEN Moonraker Component - The Conductor
    
    Monitors printer state and triggers LED effects.
    """
    
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.config = config
        
        # Config from moonraker.conf
        self.config_path = config.get("config_path", "~/printer_data/config/lumen.cfg")
        # debug: False, True (journal only), or "console" (journal + Mainsail)
        debug_val = config.get("debug", "false").lower()
        self.debug = debug_val in ("true", "console")
        self.debug_console = debug_val == "console"
        
        # Settings (loaded from lumen.cfg)
        self.temp_floor = 25.0
        self.bored_timeout = 300.0
        self.sleep_timeout = 600.0
        self.max_brightness = 0.4
        self.update_rate = 0.1
        self.update_rate_printing = 1.0
        self.gpio_fps = 60
        # Bed dimensions for KITT tracking
        self.bed_x_min = 0.0
        self.bed_x_max = 300.0
        self.bed_y_min = 0.0
        self.bed_y_max = 300.0

        # Macro tracking for state detection (v1.2.0)
        self.macro_homing: List[str] = []
        self.macro_meshing: List[str] = []
        self.macro_leveling: List[str] = []
        self.macro_probing: List[str] = []
        self.macro_paused: List[str] = []
        self.macro_cancelled: List[str] = []
        self.macro_filament: List[str] = []
        self._active_macro_state: Optional[str] = None  # Current macro-triggered state
        self._macro_start_time: float = 0.0

        # LED groups, drivers, effects
        self.led_groups: Dict[str, Dict[str, Any]] = {}
        self.event_mappings: Dict[str, List[Dict[str, str]]] = {}
        self.effect_settings: Dict[str, Dict[str, str]] = {}
        self.drivers: Dict[str, LEDDriver] = {}
        self.effect_states: Dict[str, EffectState] = {}
        self.effect_instances: Dict[str, Any] = {}  # Cache effect instances (one per effect type)
        
        # Config validation warnings (collected during load)
        self.config_warnings: List[str] = []
        
        # Animation loop
        self._animation_task: Optional[asyncio.Task] = None
        self._animation_running = False
        # v1.5.0: Per-group last update time for selective driver updates
        self._last_group_update: Dict[str, float] = {}
        
        # Thermal logging throttle (v1.0.0 - performance optimization)
        self._last_thermal_log: Dict[str, Tuple[float, float, float]] = {}  # group_name -> (time, current_temp, target_temp)

        # v1.4.0 - Performance: Cache driver intervals to avoid isinstance() checks in hot path
        self._driver_intervals: Dict[str, Tuple[float, float]] = {}  # group_name -> (printing_interval, idle_interval)

        # v1.5.0 - FPS tracking for status endpoint (lightweight rolling average)
        self._frame_times: List[float] = []  # Last 30 frame timestamps
        self._max_frame_samples = 30  # Keep last 30 frames for 0.5-2 second average at 15-60 FPS

        # v1.5.0 - Performance metrics tracking
        self._perf_max_frame_time = 0.0  # Worst case frame time (ms)
        self._perf_console_sends = 0  # Total console sends since startup
        self._perf_console_send_times: List[float] = []  # Last 60 console send timestamps (1 minute window)
        self._perf_animation_start_time: Optional[float] = None  # Animation loop start time

        # v1.7.0 - Test mode for effect/state debugging
        self._test_mode_enabled = False
        self._test_mode_state_index = 0  # Current state being tested
        self._test_mode_effect_index = 0  # Current effect being tested
        self._test_mode_group = ""  # Group being tested (for effect cycling)
        self._test_mode_states = sorted([e.value for e in PrinterEvent])  # All available states
        self._test_mode_effects = sorted(EFFECT_REGISTRY.keys())  # All available effects

        # v1.7.0 - Performance profiling
        self.profiling_enabled = False  # Loaded from config
        self._profiling_task: Optional[asyncio.Task] = None

        # Load config and create drivers
        self._load_config()
        self._create_drivers()
        for name in self.drivers:
            self.effect_states[name] = EffectState()

        # v1.4.0 - Cache driver update intervals
        self._cache_driver_intervals()
        
        # State detection
        self.printer_state = PrinterState()
        self.state_detector = StateDetector(
            temp_floor=self.temp_floor,
            bored_timeout=self.bored_timeout,
            sleep_timeout=self.sleep_timeout,
        )
        self.klippy_ready = False
        
        # Register handlers
        self.server.register_event_handler("server:klippy_ready", self._on_klippy_ready)
        self.server.register_event_handler("server:klippy_shutdown", self._on_klippy_shutdown)
        self.server.register_event_handler("server:klippy_disconnected", self._on_klippy_disconnected)
        self.server.register_event_handler("server:status_update", self._on_status_update)
        self.server.register_event_handler("server:gcode_response", self._on_gcode_response)
        self.server.register_event_handler("server:exit", self._on_server_shutdown)
        self.state_detector.add_listener(self._on_event_change)
        
        # Register API endpoints
        self.server.register_endpoint("/server/lumen/status", ["GET"], self._handle_status)
        self.server.register_endpoint("/server/lumen/colors", ["GET"], self._handle_colors)
        self.server.register_endpoint("/server/lumen/test_event", ["POST"], self._handle_test_event)
        self.server.register_endpoint("/server/lumen/reload", ["POST"], self._handle_reload)
        # v1.6.5: New API endpoints
        self.server.register_endpoint("/server/lumen/effects", ["GET"], self._handle_effects)
        self.server.register_endpoint("/server/lumen/set_group", ["POST"], self._handle_set_group)
        # v1.7.0: Test mode endpoints (flat paths for Klipper macro compatibility)
        self.server.register_endpoint("/server/lumen/test_start", ["POST"], self._handle_test_start)
        self.server.register_endpoint("/server/lumen/test_stop", ["POST"], self._handle_test_stop)
        self.server.register_endpoint("/server/lumen/test_next_state", ["POST"], self._handle_test_next_state)
        self.server.register_endpoint("/server/lumen/test_prev_state", ["POST"], self._handle_test_prev_state)
        self.server.register_endpoint("/server/lumen/test_next_effect", ["POST"], self._handle_test_next_effect)
        self.server.register_endpoint("/server/lumen/test_prev_effect", ["POST"], self._handle_test_prev_effect)
        
        # Log initialization
        self._log_info(f"Initialized with {len(self.led_groups)} groups")
        if self.config_warnings:
            for warn in self.config_warnings:
                self._log_warning(warn)

    # ─────────────────────────────────────────────────────────────
    # Task Exception Handling
    # ─────────────────────────────────────────────────────────────

    def _task_exception_handler(self, task: asyncio.Task) -> None:
        """Handle exceptions from fire-and-forget tasks."""
        try:
            task.result()  # This will raise if task failed
        except asyncio.CancelledError:
            pass  # Expected during shutdown
        except Exception as e:
            self._log_error(f"Unhandled exception in background task: {e}")
            import traceback
            traceback.print_exc()

    # ─────────────────────────────────────────────────────────────
    # Logging Helpers (respects debug setting)
    # ─────────────────────────────────────────────────────────────
    
    def _log_debug(self, msg: str, to_console: bool = True) -> None:
        """Log debug message (only if debug enabled).

        Args:
            msg: Message to log
            to_console: If True and debug_console enabled, also send to Mainsail

        Behavior:
            debug: False   → No logging
            debug: True    → Journal only (systemd/journalctl)
            debug: console → Journal + Mainsail console
        """
        if not self.debug:
            return  # Debug disabled, no logging

        # Always log to journal when debug enabled
        _logger.info(f"[LUMEN] {msg}")

        # Additionally send to Mainsail console if debug: console
        if to_console and self.debug_console:
            task = asyncio.create_task(self._console_log(msg))
            task.add_done_callback(self._task_exception_handler)
    
    async def _console_log(self, msg: str) -> None:
        """Send message to Mainsail console via Klipper RESPOND."""
        if not self.klippy_ready:
            return
        try:
            # v1.5.0: Track console send rate for performance monitoring
            now = time.time()
            self._perf_console_sends += 1
            self._perf_console_send_times.append(now)
            # Keep only last 60 timestamps (1 minute window at 1 send/second)
            if len(self._perf_console_send_times) > 60:
                self._perf_console_send_times.pop(0)

            klippy = self.server.lookup_component("klippy_apis")
            # Escape quotes in message
            safe_msg = msg.replace('"', "'")
            await klippy.run_gcode(f'RESPOND PREFIX="LUMEN" MSG="{safe_msg}"')
        except Exception as e:
            # v1.4.0: Log exception for debugging (Klipper may be busy or not ready)
            self._log_debug(f"Failed to send console message: {e}")
    
    def _log_info(self, msg: str) -> None:
        """Log info message (always)."""
        _logger.info(f"[LUMEN] {msg}")
    
    def _log_warning(self, msg: str) -> None:
        """Log warning message (always). v1.5.0: Also send to console if debug enabled."""
        _logger.warning(f"[LUMEN] {msg}")
        if self.debug_console:
            # Send warning to Mainsail console
            asyncio.create_task(self._send_console_msg(f"WARNING: {msg}"))
    
    def _log_error(self, msg: str) -> None:
        """Log error message (always). v1.5.0: Also send to console if debug enabled."""
        _logger.error(f"[LUMEN] {msg}")
        if self.debug_console:
            # Send error to Mainsail console
            asyncio.create_task(self._send_console_msg(f"ERROR: {msg}"))
    
    # ─────────────────────────────────────────────────────────────
    # Config Loading
    # ─────────────────────────────────────────────────────────────
    
    def _load_config(self) -> None:
        """Load and parse lumen.cfg with validation."""
        path = Path(self.config_path).expanduser()
        if not path.exists():
            self._log_warning(f"Config not found: {path}")
            return
        
        # Clear previous state for reload
        self.led_groups.clear()
        self.event_mappings.clear()
        self.effect_settings.clear()
        self.config_warnings.clear()
        
        try:
            with open(path, 'r') as f:
                lines = f.readlines()
            
            current_section = None
            current_section_line = 0
            current_data: Dict[str, str] = {}
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    if current_section:
                        self._process_section(current_section, current_data, current_section_line)
                    current_section = line[1:-1]
                    current_section_line = line_num
                    current_data = {}
                elif ':' in line and current_section:
                    key, value = line.split(':', 1)
                    # Strip inline comments (# ...)
                    if '#' in value:
                        value = value.split('#', 1)[0]
                    current_data[key.strip()] = value.strip()
            
            if current_section:
                self._process_section(current_section, current_data, current_section_line)
            
            # Validate all event mappings have valid colors
            self._validate_config()
            
            self._log_info(f"Loaded: {len(self.led_groups)} groups, {len(self.event_mappings)} events")
        except Exception as e:
            self._log_error(f"Config error: {e}")
    
    def _validate_config(self) -> None:
        """Validate configuration and collect warnings.

        v1.5.0: More strict validation - reject invalid effect/event names entirely.
        """
        available_colors = list_colors()
        valid_effects = set(EFFECT_REGISTRY.keys())
        # v1.2.0 - Added macro-triggered states
        valid_events = {
            "idle", "heating", "printing", "cooldown", "error", "bored", "sleep",
            "homing", "meshing", "leveling", "probing", "paused", "cancelled", "filament"
        }

        # Effects that require addressable LEDs (not compatible with PWM driver)
        addressable_only_effects = {"disco", "thermal", "progress"}

        # Check event mappings
        for event_name, mappings in self.event_mappings.items():
            if event_name not in valid_events:
                # v1.5.0: Reject invalid event names (was warning before)
                raise ValueError(f"Unknown event '{event_name}' in config. Valid events: {', '.join(sorted(valid_events))}")

            for mapping in mappings:
                effect = mapping.get("effect", "")
                color = mapping.get("color")
                group = mapping.get("group", "?")

                # Get group driver type
                group_config = self.led_groups.get(group, {})
                driver_type = group_config.get("driver", "klipper")

                # PWM groups use brightness values, not effect names
                if driver_type == "pwm":
                    if not self._is_pwm_value(effect):
                        self.config_warnings.append(
                            f"Group '{group}' on_{event_name}: invalid PWM value '{effect}' (valid: on, off, dim, or 0.0-1.0)"
                        )
                else:
                    # Validate effect name for addressable LED groups
                    if effect not in valid_effects:
                        # v1.5.0: Reject invalid effect names (was warning before)
                        raise ValueError(
                            f"Group '{group}' on_{event_name}: unknown effect '{effect}'. Valid effects: {', '.join(sorted(valid_effects))}"
                        )

                    # Warn if using addressable-only effects with PWM driver
                    if driver_type == "pwm" and effect in addressable_only_effects:
                        self.config_warnings.append(
                            f"Group '{group}' on_{event_name}: effect '{effect}' requires addressable LEDs (not compatible with PWM driver). Use 'solid', 'pulse', or 'heartbeat' instead."
                        )

                    # Validate color name (if specified)
                    if color and color.lower() not in available_colors:
                        self.config_warnings.append(
                            f"Group '{group}' on_{event_name}: unknown color '{color}' (check /server/lumen/colors for list)"
                        )

        # Check LED groups have required fields
        for group_name, group_config in self.led_groups.items():
            driver = group_config.get("driver", "klipper")
            if driver == "klipper" and not group_config.get("neopixel"):
                self.config_warnings.append(f"Group '{group_name}': missing 'neopixel' for klipper driver")
            elif driver == "pwm" and not group_config.get("pin_name"):
                self.config_warnings.append(f"Group '{group_name}': missing 'pin_name' for pwm driver")
    
    def _is_pwm_value(self, value: str) -> bool:
        """Check if value is a PWM brightness value (on, off, dim, or 0.0-1.0)."""
        if value.lower() in ("on", "off", "dim"):
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def _process_section(self, section: str, data: Dict[str, str], line_num: int = 0) -> None:
        """Process a config section."""
        try:
            parts = section.split(None, 1)
            section_type = parts[0]
            section_name = parts[1] if len(parts) > 1 else None
            
            if section_type == "lumen_settings":
                # v1.5.0: Validate numeric values with proper bounds checking
                self.temp_floor = float(data.get("temp_floor", self.temp_floor))
                self.bored_timeout = float(data.get("bored_timeout", self.bored_timeout))
                self.sleep_timeout = float(data.get("sleep_timeout", self.sleep_timeout))

                # v1.5.0: max_brightness is deprecated - use group_brightness per group instead
                if "max_brightness" in data:
                    max_brightness = float(data.get("max_brightness", self.max_brightness))
                    if not 0.0 <= max_brightness <= 1.0:
                        raise ValueError(f"max_brightness must be 0.0-1.0, got {max_brightness}")
                    self.max_brightness = max_brightness
                    self.config_warnings.append(
                        "DEPRECATED: max_brightness in [lumen_settings] is no longer used. "
                        "Use group_brightness in each [lumen_group] instead for per-group control."
                    )

                # Validate update rates (> 0)
                update_rate = float(data.get("update_rate", self.update_rate))
                if update_rate <= 0:
                    raise ValueError(f"update_rate must be > 0, got {update_rate}")
                self.update_rate = update_rate

                update_rate_printing = float(data.get("update_rate_printing", self.update_rate_printing))
                if update_rate_printing <= 0:
                    raise ValueError(f"update_rate_printing must be > 0, got {update_rate_printing}")
                self.update_rate_printing = update_rate_printing

                # Validate GPIO FPS (1-120 reasonable range)
                gpio_fps = int(data.get("gpio_fps", self.gpio_fps))
                if not 1 <= gpio_fps <= 120:
                    raise ValueError(f"gpio_fps must be 1-120, got {gpio_fps}")
                self.gpio_fps = gpio_fps
                # Bed dimensions for KITT tracking
                self.bed_x_min = float(data.get("bed_x_min", self.bed_x_min))
                self.bed_x_max = float(data.get("bed_x_max", self.bed_x_max))
                self.bed_y_min = float(data.get("bed_y_min", self.bed_y_min))
                self.bed_y_max = float(data.get("bed_y_max", self.bed_y_max))
                # Macro tracking (v1.2.0) - comma-separated lists
                self.macro_homing = self._parse_macro_list(data.get("macro_homing", ""))
                self.macro_meshing = self._parse_macro_list(data.get("macro_meshing", ""))
                self.macro_leveling = self._parse_macro_list(data.get("macro_leveling", ""))
                self.macro_probing = self._parse_macro_list(data.get("macro_probing", ""))
                self.macro_paused = self._parse_macro_list(data.get("macro_paused", ""))
                self.macro_cancelled = self._parse_macro_list(data.get("macro_cancelled", ""))
                self.macro_filament = self._parse_macro_list(data.get("macro_filament", ""))
                # v1.7.0 - Performance profiling
                profiling_str = data.get("profiling_enabled", "false").lower()
                self.profiling_enabled = profiling_str in ("true", "1", "yes")
            
            elif section_type == "lumen_effect" and section_name:
                # v1.5.0: Validate effect parameters before storing
                validated_data = self._validate_effect_params(section_name, data)
                # v1.6.0: Validate color names in effect settings
                self._validate_colors_in_effect_settings(section_name, validated_data)
                self.effect_settings[section_name] = validated_data
            
            elif section_type == "lumen_group" and section_name:
                # v1.5.0: Validate group_brightness (0.0-1.0)
                group_brightness = float(data.get("group_brightness", 1.0))
                if not 0.0 <= group_brightness <= 1.0:
                    raise ValueError(f"[lumen_group {section_name}] group_brightness must be 0.0-1.0, got {group_brightness}")

                self.led_groups[section_name] = {
                    "driver": data.get("driver", "klipper"),
                    "neopixel": data.get("neopixel"),
                    "gpio_pin": int(data.get("gpio_pin", 18)) if "gpio_pin" in data else None,
                    "proxy_host": data.get("proxy_host", "127.0.0.1"),
                    "proxy_port": int(data.get("proxy_port", 3769)),
                    "color_order": data.get("color_order", "GRB"),
                    "index_start": int(data.get("index_start", 1)),
                    "index_end": int(data.get("index_end", 1)),
                    "pin_name": data.get("pin_name"),
                    "scale": float(data.get("scale", 10.0)),
                    "direction": data.get("direction", "standard").strip().lower(),
                    "group_brightness": group_brightness,
                }
                
                # Extract event mappings (on_idle, on_heating, etc.)
                for key, value in data.items():
                    if key.startswith("on_"):
                        event_name = key[3:]
                        parsed = self._parse_effect_color(value)

                        # v1.6.0: Validate color names during config load
                        self._validate_colors_in_mapping(section_name, event_name, parsed)

                        if event_name not in self.event_mappings:
                            self.event_mappings[event_name] = []
                        # Store full parsed dict plus group name
                        mapping = {"group": section_name, **parsed}
                        self.event_mappings[event_name].append(mapping)
        except Exception as e:
            loc = f" (line {line_num})" if line_num else ""
            self._log_error(f"Error in section [{section}]{loc}: {e}")

    def _validate_effect_params(self, effect_name: str, data: Dict[str, str]) -> Dict[str, str]:
        """Validate effect parameters and return validated copy.

        v1.5.0: Validate numeric ranges for brightness, speed, sparkle, etc.
        Raises ValueError if validation fails.
        """
        validated = data.copy()

        # Validate brightness parameters (0.0-1.0)
        for key in ['min_brightness', 'max_brightness']:
            if key in validated:
                value = float(validated[key])
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"[lumen_effect {effect_name}] {key} must be 0.0-1.0, got {value}")

        # Validate speed (> 0)
        if 'speed' in validated:
            value = float(validated['speed'])
            if value <= 0:
                raise ValueError(f"[lumen_effect {effect_name}] speed must be > 0, got {value}")

        # Validate sparkle parameters (integers, min <= max)
        if 'min_sparkle' in validated or 'max_sparkle' in validated:
            min_sparkle = int(validated.get('min_sparkle', 1))
            max_sparkle = int(validated.get('max_sparkle', 6))

            if min_sparkle < 0:
                raise ValueError(f"[lumen_effect {effect_name}] min_sparkle must be >= 0, got {min_sparkle}")
            if max_sparkle < 1:
                raise ValueError(f"[lumen_effect {effect_name}] max_sparkle must be >= 1, got {max_sparkle}")
            if min_sparkle > max_sparkle:
                raise ValueError(f"[lumen_effect {effect_name}] min_sparkle ({min_sparkle}) must be <= max_sparkle ({max_sparkle})")

        # Validate gradient_curve (> 0)
        if 'gradient_curve' in validated:
            value = float(validated['gradient_curve'])
            if value <= 0:
                raise ValueError(f"[lumen_effect {effect_name}] gradient_curve must be > 0, got {value}")

        # Validate cooling/fade rates (0.0-1.0)
        for key in ['fire_cooling', 'comet_fade_rate']:
            if key in validated:
                value = float(validated[key])
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"[lumen_effect {effect_name}] {key} must be 0.0-1.0, got {value}")

        # Validate positive integers
        for key in ['comet_tail_length', 'chase_size', 'kitt_eye_size', 'kitt_tail_length']:
            if key in validated:
                value = int(validated[key])
                if value < 1:
                    raise ValueError(f"[lumen_effect {effect_name}] {key} must be >= 1, got {value}")

        # Validate rainbow_spread (0.0-1.0)
        if 'rainbow_spread' in validated:
            value = float(validated['rainbow_spread'])
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"[lumen_effect {effect_name}] rainbow_spread must be 0.0-1.0, got {value}")

        return validated

    def _validate_colors_in_effect_settings(self, effect_name: str, data: Dict[str, str]) -> None:
        """
        Validate color names in effect settings during config load (v1.6.0).

        Raises ValueError if any color name is invalid, preventing config load.

        Args:
            effect_name: Effect name (chase, kitt, etc.)
            data: Effect settings dict
        """
        # Color parameters that might be present in effect settings
        color_params = [
            'base_color',         # kitt, fire
            'chase_color_1',      # chase
            'chase_color_2',      # chase
        ]

        for param in color_params:
            if param in data:
                color_name = data[param]
                try:
                    get_color(color_name)
                except ValueError:
                    raise ValueError(
                        f"[lumen_effect {effect_name}] {param}: "
                        f"Invalid color '{color_name}'. Use /server/lumen/colors for list of valid colors."
                    )

    def _validate_colors_in_mapping(self, group_name: str, event_name: str, parsed: Dict[str, Any]) -> None:
        """
        Validate color names in effect mapping during config load (v1.6.0).

        Raises ValueError if any color name is invalid, preventing config load.
        This provides immediate feedback instead of silent fallback at runtime.

        Args:
            group_name: LED group name
            event_name: Event name (idle, heating, etc.)
            parsed: Parsed effect mapping dict
        """
        # Check single color (for effects like solid, pulse, etc.)
        if parsed.get("color"):
            color_name = parsed["color"]
            try:
                get_color(color_name)
            except ValueError:
                raise ValueError(
                    f"[lumen_group {group_name}] on_{event_name}: "
                    f"Invalid color '{color_name}'. Use /server/lumen/colors for list of valid colors."
                )

        # Check start_color (for thermal, progress)
        if parsed.get("start_color"):
            color_name = parsed["start_color"]
            try:
                get_color(color_name)
            except ValueError:
                raise ValueError(
                    f"[lumen_group {group_name}] on_{event_name}: "
                    f"Invalid start_color '{color_name}'. Use /server/lumen/colors for list of valid colors."
                )

        # Check end_color (for thermal, progress)
        if parsed.get("end_color"):
            color_name = parsed["end_color"]
            try:
                get_color(color_name)
            except ValueError:
                raise ValueError(
                    f"[lumen_group {group_name}] on_{event_name}: "
                    f"Invalid end_color '{color_name}'. Use /server/lumen/colors for list of valid colors."
                )

    def _parse_macro_list(self, value: str) -> List[str]:
        """Parse comma-separated macro list and return uppercase list."""
        if not value or not value.strip():
            return []
        # Split by comma, strip whitespace, convert to uppercase, filter empties
        macros = [m.strip().upper() for m in value.split(",")]
        return [m for m in macros if m]

    def _parse_effect_color(self, value: str) -> Dict[str, Any]:
        """Parse effect specification with optional inline parameters.

        Formats:
            effect                           → basic effect
            effect color                     → effect with color
            effect group_num                 → multi-group effect (chase 1, chase 2, etc.)
            thermal [source] start end [curve]  → thermal with params
            progress start end [curve]       → progress with params
            comet color                      → comet with color
            kitt                             → kitt scanner

        Returns dict with: effect, color, start_color, end_color, gradient_curve, temp_source, group_num
        """
        parts = value.strip().split()
        result: Dict[str, Any] = {"effect": parts[0], "color": None, "group_num": None}

        # Check for multi-group numbering (chase 1, chase 2, etc.)
        if len(parts) >= 2 and parts[1].isdigit():
            result["group_num"] = int(parts[1])
            # Remove group number from parts for further parsing
            parts = [parts[0]] + parts[2:]

        if parts[0] == "thermal":
            # thermal [temp_source] [start_color] [end_color] [gradient_curve]
            idx = 1
            # Check if first param is a temp source
            if len(parts) > idx and parts[idx] in ("extruder", "bed", "chamber"):
                result["temp_source"] = parts[idx]
                idx += 1
            # Next two are colors
            if len(parts) > idx:
                result["start_color"] = parts[idx]
                idx += 1
            if len(parts) > idx:
                result["end_color"] = parts[idx]
                idx += 1
            # Optional gradient curve
            if len(parts) > idx:
                try:
                    result["gradient_curve"] = float(parts[idx])
                except ValueError:
                    pass
        
        elif parts[0] == "progress":
            # progress [start_color] [end_color] [gradient_curve]
            if len(parts) > 1:
                result["start_color"] = parts[1]
            if len(parts) > 2:
                result["end_color"] = parts[2]
            if len(parts) > 3:
                try:
                    result["gradient_curve"] = float(parts[3])
                except ValueError:
                    pass

        elif parts[0] in ("comet", "kitt") and len(parts) >= 2:
            # comet/kitt with color: comet blue, kitt cobalt
            result["color"] = parts[1]

        elif len(parts) >= 2:
            # Standard: effect color (or effect:color)
            if ':' in value:
                effect, color = value.split(':', 1)
                result["effect"] = effect.strip()
                result["color"] = color.strip()
            else:
                result["color"] = parts[1]
        
        return result
    
    def _create_drivers(self) -> None:
        """Create LED drivers for each group."""
        self.drivers.clear()
        for name, config in self.led_groups.items():
            driver = create_driver(name, config, self.server)
            if driver:
                self.drivers[name] = driver
                self._log_debug(f"Created driver for group '{name}': {config.get('driver', 'klipper')}")

    def _cache_driver_intervals(self) -> None:
        """Cache driver update intervals to avoid isinstance() checks in animation loop (v1.4.0 optimization)."""
        # v1.5.0: Use top-level imports (GPIODriver, ProxyDriver already imported at module level)
        # Don't do local import here - causes module identity issues

        for group_name, driver in self.drivers.items():
            driver_type = type(driver).__name__

            if isinstance(driver, (GPIODriver, ProxyDriver)):
                # GPIO/Proxy drivers use FPS-based interval (60 Hz = 0.0167s)
                interval = 1.0 / self.gpio_fps
                self._driver_intervals[group_name] = (interval, interval)  # Same for printing and idle
                self._log_debug(f"Group '{group_name}': {driver_type} → GPIO/Proxy interval={interval:.4f}s (FPS={self.gpio_fps})")
            else:
                # Klipper/PWM drivers use slower intervals (respects G-code queue)
                self._driver_intervals[group_name] = (self.update_rate_printing, self.update_rate)
                self._log_debug(f"Group '{group_name}': {driver_type} → Klipper/PWM printing={self.update_rate_printing}s, idle={self.update_rate}s")

        self._log_debug(f"Cached driver intervals for {len(self._driver_intervals)} groups")

    # ─────────────────────────────────────────────────────────────
    # Event Handlers
    # ─────────────────────────────────────────────────────────────
    
    async def _on_klippy_ready(self) -> None:
        self.klippy_ready = True
        self._log_info("Klippy ready")
        try:
            klippy_apis = self.server.lookup_component("klippy_apis")
            
            # Subscribe to status updates
            await klippy_apis.subscribe_objects({
                "webhooks": ["state", "state_message"],
                "print_stats": ["state", "filename", "info"],
                "display_status": ["progress", "message"],
                "heater_bed": ["temperature", "target"],
                "extruder": ["temperature", "target"],
                "idle_timeout": ["state"],
                "toolhead": ["position"],
                # v1.3.0 - Optional sensors (graceful if not present)
                "temperature_sensor chamber_temp": ["temperature"],
                "filament_switch_sensor filament_sensor": ["filament_detected"],
            })

            # Query current state (subscription only gives deltas)
            result = await klippy_apis.query_objects({
                "webhooks": ["state"],
                "print_stats": ["state", "filename"],
                "display_status": ["progress"],
                "heater_bed": ["temperature", "target"],
                "extruder": ["temperature", "target"],
                "idle_timeout": ["state"],
                "toolhead": ["position"],
                # v1.3.0 - Optional sensors
                "temperature_sensor chamber_temp": ["temperature"],
                "filament_switch_sensor filament_sensor": ["filament_detected"],
            })
            if result:
                self.printer_state.update_from_status(result)
                self._log_debug(f"Initial state: print={self.printer_state.print_state}, bed_target={self.printer_state.bed_target}")
            
            # Detect current event from queried state
            event = self.state_detector.update(self.printer_state)
            if event:
                await self._apply_event(event)
            else:
                await self._apply_event(PrinterEvent.IDLE)
                
        except Exception as e:
            self._log_error(f"Subscribe error: {e}")
    
    async def _on_klippy_shutdown(self) -> None:
        self.klippy_ready = False
        self._animation_running = False
        self._log_debug("Klippy shutdown")
    
    async def _on_klippy_disconnected(self) -> None:
        self.klippy_ready = False
        self._animation_running = False
        self._log_debug("Klippy disconnected")

    async def _on_server_shutdown(self) -> None:
        """Clean shutdown: stop animation loop and turn off LEDs."""
        self._log_info("Moonraker shutdown - cleaning up LUMEN")

        # Stop animation loop
        self._animation_running = False
        if self._animation_task:
            self._animation_task.cancel()
            try:
                await self._animation_task
            except asyncio.CancelledError:
                pass

        # Turn off all LEDs
        for name, driver in self.drivers.items():
            try:
                await driver.set_off()
                self._log_debug(f"Turned off LEDs for group: {name}")
            except Exception as e:
                self._log_error(f"Failed to turn off {name}: {e}")

    async def _on_status_update(self, status: Dict[str, Any]) -> None:
        self.printer_state.update_from_status(status)

        # v1.4.1: Check for macro timeout (safety - clear after 2 minutes)
        if self._active_macro_state and self._macro_start_time > 0:
            if time.time() - self._macro_start_time > 120.0:
                self._log_debug(f"Macro timeout: {self._active_macro_state} (120s elapsed)")
                self._active_macro_state = None
                self._macro_start_time = 0.0
                self.printer_state.active_macro_state = None
                self.printer_state.macro_start_time = 0.0

        new_event = self.state_detector.update(self.printer_state)
        if new_event:
            task = asyncio.create_task(self._apply_event(new_event))
            task.add_done_callback(self._task_exception_handler)

    async def _on_gcode_response(self, response: str) -> None:
        """Handle G-code responses to detect macro execution (v1.2.0)."""
        if not self.klippy_ready:
            return

        # v1.4.1: CRITICAL - Ignore our own LUMEN messages to prevent infinite loop
        if response.startswith("LUMEN") or response.startswith("// LUMEN"):
            return

        # v1.4.1: Skip probe results and most comment lines (noise reduction)
        # These flood the logs and don't contain macro names
        if response.startswith("// probe at") or response.startswith("probe at"):
            return

        # v1.4.1: Detect macro completion messages and clear macro state
        completion_markers = {
            "meshing": ["// Mesh Bed Leveling Complete", "// mesh bed leveling complete"],
            "homing": ["// Homing Complete", "// homing complete"],
            "leveling": ["// Gantry Leveling Complete", "// gantry leveling complete",
                        "// Z-Tilt Adjust Complete", "// z-tilt adjust complete"],
            "probing": ["// Probe Calibration Complete", "// probe calibration complete"],
        }

        if self._active_macro_state:
            markers = completion_markers.get(self._active_macro_state, [])
            for marker in markers:
                if marker.lower() in response.lower():
                    self._log_debug(f"Macro completion detected: {self._active_macro_state}")
                    self._active_macro_state = None
                    self._macro_start_time = 0.0
                    self.printer_state.active_macro_state = None
                    self.printer_state.macro_start_time = 0.0

                    # Force state detector to re-evaluate (return to normal state cycle)
                    new_event = self.state_detector.update(self.printer_state)
                    if new_event:
                        task = asyncio.create_task(self._apply_event(new_event))
                        task.add_done_callback(self._task_exception_handler)
                    return

        # Convert response to uppercase for case-insensitive matching
        response_upper = response.upper()

        # Check each macro type
        macro_map = {
            "homing": self.macro_homing,
            "meshing": self.macro_meshing,
            "leveling": self.macro_leveling,
            "probing": self.macro_probing,
            "paused": self.macro_paused,
            "cancelled": self.macro_cancelled,
            "filament": self.macro_filament,
        }

        for state_name, macro_list in macro_map.items():
            if not macro_list:
                continue

            for macro in macro_list:
                if macro in response_upper:
                    # Macro detected - activate macro state
                    self._active_macro_state = state_name
                    self._macro_start_time = time.time()
                    # Update PrinterState with macro info
                    self.printer_state.active_macro_state = state_name
                    self.printer_state.macro_start_time = self._macro_start_time
                    self._log_debug(f"Macro detected: {macro} → state: {state_name}")

                    # Force state detector to re-evaluate with macro state active
                    new_event = self.state_detector.update(self.printer_state)
                    if new_event:
                        task = asyncio.create_task(self._apply_event(new_event))
                        task.add_done_callback(self._task_exception_handler)
                    break

    def _on_event_change(self, event: PrinterEvent) -> None:
        """Called when printer event changes."""
        self._log_debug(f"Event: {event.value}")
    
    # ─────────────────────────────────────────────────────────────
    # Effect Application
    # ─────────────────────────────────────────────────────────────
    
    async def _apply_event(self, event: PrinterEvent) -> None:
        """Apply LED effects for an event."""
        event_name = event.value
        if event_name not in self.event_mappings:
            self._log_debug(f"No mappings for event: {event_name}")
            return
        
        self._log_debug(f"Applying event: {event_name} to {len(self.event_mappings[event_name])} groups")
        
        for mapping in self.event_mappings[event_name]:
            group_name = mapping["group"]
            
            driver = self.drivers.get(group_name)
            if not driver:
                self._log_debug(f"No driver for group: {group_name}")
                continue
            
            await self._apply_effect(group_name, driver, mapping)

        await self._ensure_animation_loop()

        # v1.5.0 Fix 7: Schedule additional cleanup task for "sleep" state
        # This ensures LEDs turn off even if animation loop is still sending updates
        if event_name == "sleep":
            asyncio.create_task(self._delayed_sleep_cleanup())
    
    async def _apply_effect(self, group_name: str, driver: LEDDriver, mapping: Dict[str, Any]) -> None:
        """Apply effect to a driver.
        
        Args:
            group_name: Name of the LED group
            driver: LED driver instance
            mapping: Parsed effect mapping with inline params
        """
        effect = mapping["effect"]
        color_name = mapping.get("color")

        # Get base color (v1.5.0: Validate color names, add warning on failure)
        if color_name:
            try:
                base_r, base_g, base_b = get_color(color_name)
            except ValueError as e:
                self._log_warning(f"Group '{group_name}': {e}. Using white as fallback.")
                if str(e) not in [w for w in self.config_warnings]:
                    self.config_warnings.append(str(e))
                base_r, base_g, base_b = (1.0, 1.0, 1.0)
        else:
            base_r, base_g, base_b = (1.0, 1.0, 1.0)

        # v1.5.0: Removed global brightness application - now using per-group brightness
        r = base_r
        g = base_g
        b = base_b
        
        # Get effect params from [lumen_effect] section (defaults)
        params = self.effect_settings.get(effect, {})
        speed = float(params.get("speed", 1.0))
        min_bright = float(params.get("min_brightness", 0.2))
        max_bright = float(params.get("max_brightness", 0.8))
        min_sparkle = int(params.get("min_sparkle", 1))
        max_sparkle = int(params.get("max_sparkle", 6))

        # Thermal/Progress fill params - inline overrides [lumen_effect] defaults
        start_color_name = mapping.get("start_color") or params.get("start_color", "steel")
        end_color_name = mapping.get("end_color") or params.get("end_color", "matrix")
        gradient_curve = mapping.get("gradient_curve") or float(params.get("gradient_curve", 2.0))
        temp_source = mapping.get("temp_source") or params.get("temp_source", "extruder")

        # Rainbow params
        rainbow_spread = float(params.get("rainbow_spread", 1.0))

        # Fire params
        fire_cooling = float(params.get("fire_cooling", 0.3))

        # Comet params
        comet_tail_length = int(params.get("comet_tail_length", 10))
        comet_fade_rate = float(params.get("comet_fade_rate", 0.5))

        # Chase params (v1.5.0: Validate chase colors)
        chase_color_1_name = params.get("chase_color_1", "red")
        chase_color_2_name = params.get("chase_color_2", "blue")
        try:
            chase_color_1 = get_color(chase_color_1_name)
        except ValueError as e:
            self._log_warning(f"Group '{group_name}': Invalid chase_color_1 - {e}. Using red.")
            chase_color_1 = (1.0, 0.0, 0.0)
        try:
            chase_color_2 = get_color(chase_color_2_name)
        except ValueError as e:
            self._log_warning(f"Group '{group_name}': Invalid chase_color_2 - {e}. Using blue.")
            chase_color_2 = (0.0, 0.0, 1.0)
        chase_size = int(params.get("chase_size", 5))
        chase_offset_base = float(params.get("chase_offset_base", 0.5))
        chase_offset_variation = float(params.get("chase_offset_variation", 0.1))
        chase_proximity_threshold = float(params.get("chase_proximity_threshold", 0.15))
        chase_accel_factor = float(params.get("chase_accel_factor", 1.5))
        chase_role_swap_interval = float(params.get("chase_role_swap_interval", 7.0))
        chase_collision_pause = float(params.get("chase_collision_pause", 0.3))
        # Multi-group chase number from inline spec (chase 1, chase 2, etc.)
        chase_group_num = mapping.get("group_num")

        # KITT params
        kitt_eye_size = int(params.get("kitt_eye_size", 3))
        kitt_tail_length = int(params.get("kitt_tail_length", 8))
        kitt_tracking_axis = params.get("kitt_tracking_axis", "none").lower()
        
        # Get actual RGB for start/end colors (v1.5.0: Validate gradient colors)
        try:
            start_color = get_color(start_color_name)
        except ValueError as e:
            self._log_warning(f"Group '{group_name}': Invalid start_color - {e}. Using steel.")
            start_color = (0.5, 0.5, 0.6)
        try:
            end_color = get_color(end_color_name)
        except ValueError as e:
            self._log_warning(f"Group '{group_name}': Invalid end_color - {e}. Using matrix.")
            end_color = (0.0, 1.0, 0.3)

        # v1.5.0: Removed global brightness - now using per-group brightness in animation loop
        # start_color and end_color used as-is, group brightness applied later
        
        # Apply immediate effects FIRST (before updating state)
        # This ensures the driver shows the correct state immediately
        if effect == "off":
            # v1.5.0 Fix 5: Wait for animation loop to complete current frame before clearing
            # This prevents race condition where animation loop might send updates after our clear command
            await asyncio.sleep(0.05)  # Wait 50ms for any pending animation updates to complete

            # v1.5.0: Additional safety - explicitly clear all LEDs
            # Send per-LED off colors to ensure complete cleanup
            led_count = driver.led_count if hasattr(driver, 'led_count') else 1
            self._log_debug(f"Turning off group '{group_name}': led_count={led_count}, driver={type(driver).__name__}")
            if hasattr(driver, 'set_leds') and led_count > 1:
                # Use set_leds for multi-LED groups to ensure all LEDs are cleared
                await driver.set_leds([(0.0, 0.0, 0.0)] * led_count)
                self._log_debug(f"Group '{group_name}': sent {led_count} black colors via set_leds()")

                # v1.5.0 Fix 5: Send a second clear command after a delay to ensure it takes effect
                await asyncio.sleep(0.05)  # Wait another 50ms
                await driver.set_leds([(0.0, 0.0, 0.0)] * led_count)
                self._log_debug(f"Group '{group_name}': sent second clear command to ensure LEDs are off")
            else:
                # Fall back to set_off for single LED or drivers without set_leds
                await driver.set_off()
                self._log_debug(f"Group '{group_name}': called set_off()")

                # v1.5.0 Fix 5: Send a second clear command
                await asyncio.sleep(0.05)
                await driver.set_off()
                self._log_debug(f"Group '{group_name}': sent second off command to ensure LED is off")
        elif effect == "solid":
            await driver.set_color(r, g, b)
        elif effect in ("pulse", "heartbeat", "disco"):
            await driver.set_color(r, g, b)
        else:
            await driver.set_color(r, g, b)

        # Update effect state AFTER applying immediate effect
        # This prevents race condition with animation loop
        state = self.effect_states.get(group_name)
        if state:
            # Clear old cached effect instance if effect type changed
            old_effect = state.effect
            if old_effect != effect:
                old_cache_key = f"{group_name}:{old_effect}"
                self.effect_instances.pop(old_cache_key, None)

            state.effect = effect
            state.base_color = (r, g, b)
            state.color = (r, g, b)
            state.start_time = time.time()
            state.last_update = 0.0
            state.speed = speed
            state.min_brightness = min_bright
            state.max_brightness = max_bright
            state.min_sparkle = min_sparkle
            state.max_sparkle = max_sparkle
            # Thermal/Progress
            state.start_color = start_color
            state.end_color = end_color
            state.gradient_curve = float(gradient_curve)
            state.temp_source = temp_source
            # Rainbow
            state.rainbow_spread = rainbow_spread
            # Fire
            state.fire_cooling = fire_cooling
            # Comet
            state.comet_tail_length = comet_tail_length
            state.comet_fade_rate = comet_fade_rate
            # Chase
            state.chase_color_1 = chase_color_1
            state.chase_color_2 = chase_color_2
            state.chase_size = chase_size
            state.chase_offset_base = chase_offset_base
            state.chase_offset_variation = chase_offset_variation
            state.chase_proximity_threshold = chase_proximity_threshold
            state.chase_accel_factor = chase_accel_factor
            state.chase_role_swap_interval = chase_role_swap_interval
            state.chase_collision_pause = chase_collision_pause
            state.chase_group_num = chase_group_num
            # KITT
            state.kitt_eye_size = kitt_eye_size
            state.kitt_tail_length = kitt_tail_length
            state.kitt_tracking_axis = kitt_tracking_axis
            # Direction (default to 'standard' if not set)
            group_cfg = self.led_groups.get(group_name, {})
            state.direction = group_cfg.get("direction", "standard")
    
    async def _delayed_sleep_cleanup(self) -> None:
        """
        v1.5.0 Fix 7: Delayed cleanup task for sleep state.

        Waits 2 seconds after sleep event, then sends final off commands
        to all LED groups to ensure they're actually off.
        """
        await asyncio.sleep(2.0)

        # Check if we're still in sleep state
        current_event = self.state_detector.current_event
        if current_event != "sleep":
            return  # State changed, abort cleanup

        self._log_debug("Sleep cleanup: sending final off commands to all groups")

        # Send off command to all groups
        for group_name, driver in self.drivers.items():
            try:
                led_count = driver.led_count if hasattr(driver, 'led_count') else 1
                if hasattr(driver, 'set_leds') and led_count > 1:
                    await driver.set_leds([(0.0, 0.0, 0.0)] * led_count)
                    self._log_debug(f"Sleep cleanup: cleared group '{group_name}' ({led_count} LEDs)")
                else:
                    await driver.set_off()
                    self._log_debug(f"Sleep cleanup: cleared group '{group_name}'")
            except Exception as e:
                self._log_warning(f"Sleep cleanup failed for group '{group_name}': {e}")

    # ─────────────────────────────────────────────────────────────
    # Multi-Group Chase Coordination
    # ─────────────────────────────────────────────────────────────

    def _detect_chase_groups(self) -> Dict[int, List[str]]:
        """
        Detect chase groups with numbering (chase 1, chase 2, etc.).

        Returns:
            Dict mapping group_num to list of group names in that chase group.
            Empty dict if no multi-group chase detected.
        """
        # v1.5.0 Fix 8: Don't detect chase groups if current event is "sleep"
        # This prevents chase from continuing to render during sleep state
        current_event = self.state_detector.current_event
        if current_event == "sleep":
            return {}

        chase_groups: Dict[int, List[str]] = {}

        for group_name, state in self.effect_states.items():
            if state.effect != "chase":
                continue

            # Check if this group has a chase number
            # Need to look up the original event mapping to get group_num
            group_num = getattr(state, 'chase_group_num', None)
            if group_num is not None:
                if group_num not in chase_groups:
                    chase_groups[group_num] = []
                chase_groups[group_num].append(group_name)

        # Only return if we have multiple groups or numbered groups
        if chase_groups and max(chase_groups.keys()) > 0:
            return chase_groups
        return {}

    async def _render_multi_group_chase(
        self,
        chase_groups: Dict[int, List[str]],
        now: float,
        is_printing: bool
    ) -> set:
        """
        Render coordinated multi-group chase effect.

        Args:
            chase_groups: Dict mapping group numbers to group names
            now: Current time
            is_printing: Whether printer is currently printing

        Returns:
            Set of group names that were coordinated (to skip in main loop)
        """
        coordinated = set()

        # Build circular LED array in CHASE NUMBER order, respecting direction
        # Sort by chase number (1, 2, 3, ...)
        sorted_chase_nums = sorted(chase_groups.keys())

        # Build mapping: circular_position -> (group_name, electrical_index)
        circular_led_map = []  # List of (group_name, electrical_index)

        for chase_num in sorted_chase_nums:
            for group_name in chase_groups[chase_num]:
                group_cfg = self.led_groups.get(group_name, {})
                index_start = int(group_cfg.get('index_start', 1))
                index_end = int(group_cfg.get('index_end', 1))
                direction = group_cfg.get('direction', 'standard')

                # Build circular array based on direction
                # direction: standard → add electrical indices ascending (1,2,3,...,18)
                # direction: reverse → add electrical indices descending (18,17,16,...,1)
                led_count = index_end - index_start + 1

                if direction == 'reverse':
                    # Add in descending order
                    for electrical_idx in range(index_end, index_start - 1, -1):
                        circular_led_map.append((group_name, electrical_idx))
                else:
                    # Add in ascending order
                    for electrical_idx in range(index_start, index_end + 1):
                        circular_led_map.append((group_name, electrical_idx))

                coordinated.add(group_name)

                # v1.5.0: Removed verbose chase debug log (spammed console at 60 FPS)

        if not circular_led_map:
            return coordinated

        total_leds = len(circular_led_map)

        # Get master state from first chase group
        first_group_name = chase_groups[sorted_chase_nums[0]][0]
        master_state = self.effect_states.get(first_group_name)
        if not master_state:
            return coordinated

        # Get or create chase effect instance
        cache_key = f"_multi_chase:{':'.join([name for name, _ in circular_led_map])}"
        if cache_key not in self.effect_instances:
            from .lumen_lib.effects import ChaseEffect
            self.effect_instances[cache_key] = ChaseEffect()
        chase_effect = self.effect_instances[cache_key]

        # Calculate full circular array
        state_data = {"multi_group_info": {}}
        circular_colors, needs_update = chase_effect.calculate(
            master_state, now, total_leds, state_data
        )

        # v1.5.0: Removed verbose multi-chase debug log (spammed console at 60 FPS)

        if not needs_update:
            return coordinated

        # Map circular array colors back to electrical indices for each group
        # circular_led_map contains: [(group_name, electrical_index), ...]
        # circular_colors contains: [color_for_pos_0, color_for_pos_1, ...]

        # Build color map: (group_name, electrical_index) -> color
        group_electrical_colors = {}  # group_name -> {electrical_index: color}

        for circ_pos, (group_name, electrical_idx) in enumerate(circular_led_map):
            if group_name not in group_electrical_colors:
                group_electrical_colors[group_name] = {}
            group_electrical_colors[group_name][electrical_idx] = circular_colors[circ_pos]

        # Send colors to each group's driver
        for group_name in coordinated:
            driver = self.drivers.get(group_name)
            if not driver or group_name not in group_electrical_colors:
                continue

            # v1.4.1: Skip Klipper drivers during macro states (G-code queue blocked)
            if self._active_macro_state and isinstance(driver, KlipperDriver):
                continue

            group_cfg = self.led_groups.get(group_name, {})
            index_start = int(group_cfg.get('index_start', 1))
            index_end = int(group_cfg.get('index_end', 1))
            direction = group_cfg.get('direction', 'standard')

            # Build color array in electrical order (index_start to index_end)
            electrical_colors = []
            for electrical_idx in range(index_start, index_end + 1):
                color = group_electrical_colors[group_name].get(electrical_idx)
                electrical_colors.append(color)

            # Note: No direction reversal needed here
            # The circular array was already built with direction in mind
            # (see lines 771-778 where we add indices in reverse order if direction='reverse')

            # Send to driver
            try:
                if hasattr(driver, 'set_leds'):
                    await driver.set_leds(electrical_colors)
                    # v1.5.0: Removed verbose color send debug log (spammed console at 60 FPS)
            except Exception as e:
                self._log_error(f"Multi-chase error in {group_name}: {e}")

        return coordinated

    # ─────────────────────────────────────────────────────────────
    # Animation Loop
    # ─────────────────────────────────────────────────────────────

    async def _ensure_animation_loop(self) -> None:
        """Start/stop animation loop based on active effects."""
        # Check if any effect needs animation (not "off" or "solid")
        static_effects = {"off", "solid"}
        has_animated = any(s.effect not in static_effects for s in self.effect_states.values())

        if has_animated and not self._animation_running:
            # Cancel any existing task before starting new one
            if self._animation_task and not self._animation_task.done():
                self._animation_task.cancel()
                try:
                    await self._animation_task
                except asyncio.CancelledError:
                    pass

            self._animation_running = True
            self._animation_task = asyncio.create_task(self._animation_loop())
            # v1.7.0: Start profiling task if enabled
            if self.profiling_enabled and not self._profiling_task:
                self._profiling_task = asyncio.create_task(self._profiling_loop())
        elif not has_animated and self._animation_running:
            self._animation_running = False
            if self._animation_task:
                self._animation_task.cancel()
                try:
                    await self._animation_task
                except asyncio.CancelledError:
                    pass
            # v1.7.0: Stop profiling task
            if self._profiling_task:
                self._profiling_task.cancel()
                try:
                    await self._profiling_task
                except asyncio.CancelledError:
                    pass
                self._profiling_task = None
    
    async def _animation_loop(self) -> None:
        """Background loop for animated effects."""
        try:
            # v1.5.0: Track animation start time for performance metrics
            if self._perf_animation_start_time is None:
                self._perf_animation_start_time = time.time()

            while self._animation_running:
                now = time.time()
                is_printing = self.printer_state.print_state == "printing"

                # v1.5.0: Track frame time for FPS calculation (lightweight - no overhead)
                self._frame_times.append(now)
                if len(self._frame_times) > self._max_frame_samples:
                    self._frame_times.pop(0)  # Keep only last N frames

                # v1.4.0: Build state_data once per cycle (optimization - was rebuilt for each effect)
                state_data_cache = {
                    # Temps for thermal effect
                    'bed_temp': self.printer_state.bed_temp,
                    'bed_target': self.printer_state.bed_target,
                    'extruder_temp': self.printer_state.extruder_temp,
                    'extruder_target': self.printer_state.extruder_target,
                    # v1.3.0 - Chamber temperature
                    'chamber_temp': self.printer_state.chamber_temp,
                    'chamber_target': self.printer_state.chamber_target,
                    'temp_floor': self.temp_floor,
                    # Progress for progress effect
                    'print_progress': self.printer_state.progress,
                    # Toolhead position for KITT tracking
                    'toolhead_pos_x': self.printer_state.position_x,
                    'toolhead_pos_y': self.printer_state.position_y,
                    'toolhead_pos_z': self.printer_state.position_z,
                    # Bed dimensions
                    'bed_x_min': self.bed_x_min,
                    'bed_x_max': self.bed_x_max,
                    'bed_y_min': self.bed_y_min,
                    'bed_y_max': self.bed_y_max,
                }

                # v1.5.0: Track next update times for selective driver updates
                next_update_times = []

                # v1.5.0: Collect ProxyDriver updates for batching
                # Key: (proxy_host, proxy_port), Value: list of update dicts
                proxy_batches: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}

                # Detect multi-group chase coordination
                # v1.5.0 Fix 6: Skip chase rendering if any group is "off" to prevent LEDs staying on
                chase_groups = self._detect_chase_groups()
                coordinated_groups = set()
                if chase_groups:
                    # Check if any chase group has been switched to "off" effect
                    has_off_groups = False
                    for group_names in chase_groups.values():
                        for group_name in group_names:
                            state = self.effect_states.get(group_name)
                            if state and state.effect == "off":
                                has_off_groups = True
                                break
                        if has_off_groups:
                            break

                    # Only render chase if no groups are off
                    if not has_off_groups:
                        coordinated_groups = await self._render_multi_group_chase(chase_groups, now, is_printing)

                    # Add next update times for coordinated chase groups
                    for group_name in coordinated_groups:
                        if group_name in self._driver_intervals:
                            printing_interval, idle_interval = self._driver_intervals[group_name]
                            group_interval = printing_interval if is_printing else idle_interval
                            last_update = self._last_group_update.get(group_name, 0.0)
                            next_update = last_update + group_interval
                            next_update_times.append(next_update)
                            self._last_group_update[group_name] = now

                for group_name, state in self.effect_states.items():
                    # Skip groups that are part of multi-group chase coordination
                    if group_name in coordinated_groups:
                        continue

                    # v1.5.0: Skip rendering for "off" effect - already handled in immediate application
                    if state.effect == "off":
                        continue

                    # Check if effect exists in registry
                    effect_class = EFFECT_REGISTRY.get(state.effect)
                    if not effect_class:
                        continue

                    driver = self.drivers.get(group_name)
                    if not driver:
                        continue

                    # v1.4.1: Skip Klipper drivers during macro states (G-code queue blocked, causes timeout spam)
                    if self._active_macro_state and isinstance(driver, KlipperDriver):
                        continue

                    # v1.5.0: Selective driver updates - check if interval elapsed
                    if group_name in self._driver_intervals:
                        printing_interval, idle_interval = self._driver_intervals[group_name]
                        group_interval = printing_interval if is_printing else idle_interval

                        # Check if enough time has passed since last update
                        last_update = self._last_group_update.get(group_name, 0.0)
                        time_since_update = now - last_update

                        if time_since_update < group_interval:
                            # Not time to update this group yet
                            next_update = last_update + group_interval
                            next_update_times.append(next_update)
                            continue

                        # Time to update - track next update time
                        next_update = now + group_interval
                        next_update_times.append(next_update)
                    else:
                        continue  # Skip if interval not cached (shouldn't happen)

                    try:
                        # Get cached effect instance (one per group+effect combo)
                        # IMPORTANT: Cache key must be unique per group to prevent state corruption
                        cache_key = f"{group_name}:{state.effect}"
                        if cache_key not in self.effect_instances:
                            self.effect_instances[cache_key] = effect_class()
                        effect = self.effect_instances[cache_key]

                        led_count = driver.led_count if hasattr(driver, 'led_count') else 1

                        # v1.4.0: Use cached state_data instead of rebuilding (performance optimization)
                        state_data = state_data_cache if effect.requires_state_data else None

                        # v1.5.0: Throttle thermal debug logging (disabled during printing to reduce Klipper load)
                        if state.effect == "thermal" and state_data and not is_printing:
                            current_temp = state_data.get(f'{state.temp_source}_temp', 0.0)
                            target_temp = state_data.get(f'{state.temp_source}_target', 0.0)

                            should_log = False
                            if group_name in self._last_thermal_log:
                                last_time, last_current, last_target = self._last_thermal_log[group_name]
                                temp_changed = abs(current_temp - last_current) >= 1.0 or abs(target_temp - last_target) >= 1.0
                                time_elapsed = now - last_time >= 10.0
                                should_log = temp_changed or time_elapsed
                            else:
                                should_log = True

                            if should_log:
                                self._last_thermal_log[group_name] = (now, current_temp, target_temp)
                                self._log_debug(f"Thermal {group_name}: source={state.temp_source}, current={current_temp:.1f}, target={target_temp:.1f}, floor={self.temp_floor}")

                        # Calculate effect colors
                        colors, needs_update = effect.calculate(state, now, led_count, state_data)

                        if not needs_update:
                            continue

                        # Update last_update time for effects that use it
                        if state.effect in ("disco",):
                            state.last_update = now

                        # v1.5.0: Apply per-group brightness multiplier
                        group_config = self.led_groups.get(group_name, {})
                        group_brightness = group_config.get("group_brightness", 1.0)
                        if group_brightness != 1.0:
                            # Apply brightness to all colors in the list
                            colors = [
                                None if color is None else (color[0] * group_brightness, color[1] * group_brightness, color[2] * group_brightness)
                                for color in colors
                            ]

                        # v1.5.0: Apply colors - batch ProxyDrivers, send others immediately
                        if isinstance(driver, ProxyDriver):
                            # Collect for batching
                            batch_key = (driver.proxy_host, driver.proxy_port)
                            if batch_key not in proxy_batches:
                                proxy_batches[batch_key] = []

                            if len(colors) == 1:
                                # Single color update
                                color = colors[0]
                                if color is None:
                                    r, g, b = 0.0, 0.0, 0.0
                                else:
                                    r, g, b = color

                                proxy_batches[batch_key].append({
                                    'type': 'set_color',
                                    'gpio_pin': driver.gpio_pin,
                                    'index_start': driver.index_start,
                                    'index_end': driver.index_end,
                                    'r': r,
                                    'g': g,
                                    'b': b,
                                    'color_order': driver.color_order,
                                })
                            else:
                                # Multi-LED update
                                proxy_batches[batch_key].append({
                                    'type': 'set_leds',
                                    'gpio_pin': driver.gpio_pin,
                                    'index_start': driver.index_start,
                                    'colors': colors,
                                    'color_order': driver.color_order,
                                })
                        else:
                            # Non-proxy drivers - send immediately (Klipper, GPIO, PWM)
                            if len(colors) == 1:
                                color = colors[0]
                                if color is None:
                                    await driver.set_off()
                                else:
                                    r, g, b = color
                                    await driver.set_color(r, g, b)
                            else:
                                if hasattr(driver, 'set_leds'):
                                    await driver.set_leds(colors)

                        # v1.5.0: Mark this group as updated
                        self._last_group_update[group_name] = now

                    except Exception as e:
                        self._log_error(f"Animation error in {group_name}: {e}")

                # v1.5.0: Send all batched ProxyDriver updates
                for (proxy_host, proxy_port), updates in proxy_batches.items():
                    if updates:
                        try:
                            await ProxyDriver.batch_update(proxy_host, proxy_port, updates)
                        except Exception as e:
                            self._log_error(f"Batch update failed for {proxy_host}:{proxy_port}: {e}")

                # v1.5.0: Sleep until next group needs updating (selective driver updates)
                # Use the earliest next update time to determine sleep interval
                if next_update_times:
                    next_update = min(next_update_times)
                    interval = max(next_update - now, 0.001)  # Clamp to 1ms minimum
                else:
                    # No groups active, use default interval
                    interval = self.update_rate

                # Clamp to maximum 1s to ensure responsive shutdown
                interval = min(interval, 1.0)

                # v1.5.0: Track max frame time for performance monitoring
                frame_end = time.time()
                frame_time_ms = (frame_end - now) * 1000.0
                if frame_time_ms > self._perf_max_frame_time:
                    self._perf_max_frame_time = frame_time_ms

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            self._log_debug("Animation loop cancelled")

    async def _profiling_loop(self) -> None:
        """
        Background loop for performance profiling (v1.7.0).

        Logs performance metrics every 60 seconds when profiling_enabled=true.
        """
        try:
            while self.profiling_enabled and self._animation_running:
                await asyncio.sleep(60.0)  # Log every 60 seconds

                # Gather metrics
                fps = self._get_current_fps()
                console_sends_per_min = self._get_console_sends_per_minute()
                max_frame_time = self._perf_max_frame_time

                # Get uptime
                uptime_seconds = time.time() - self._perf_animation_start_time if self._perf_animation_start_time else 0
                uptime_minutes = uptime_seconds / 60.0

                # Get CPU and memory (basic metrics)
                import psutil
                process = psutil.Process()
                cpu_percent = process.cpu_percent(interval=0.1)
                memory_mb = process.memory_info().rss / (1024 * 1024)

                # Log metrics
                self._log_info(
                    f"[PROFILING] FPS: {fps:.1f if fps else 0:.1f}, "
                    f"CPU: {cpu_percent:.1f}%, "
                    f"Memory: {memory_mb:.1f} MB, "
                    f"Max frame time: {max_frame_time:.2f} ms, "
                    f"Console sends/min: {console_sends_per_min:.1f}, "
                    f"Uptime: {uptime_minutes:.1f} min"
                )

                # Reset max frame time after logging
                self._perf_max_frame_time = 0.0

        except asyncio.CancelledError:
            self._log_debug("Profiling loop cancelled")
        except Exception as e:
            self._log_error(f"Profiling loop error: {e}")

    # ─────────────────────────────────────────────────────────────
    # Helper Methods
    # ─────────────────────────────────────────────────────────────

    def _get_current_fps(self) -> Optional[float]:
        """Calculate current animation FPS from recent frame times.

        Returns None if insufficient data, otherwise FPS as float.
        v1.5.0: Lightweight FPS tracking for diagnostics.
        """
        if len(self._frame_times) < 2:
            return None

        # Calculate average frame time from sample window
        time_span = self._frame_times[-1] - self._frame_times[0]
        frame_count = len(self._frame_times) - 1

        if time_span <= 0:
            return None

        return frame_count / time_span

    def _get_console_sends_per_minute(self) -> float:
        """Calculate console send rate over last minute.

        Returns console sends per minute based on rolling 60-second window.
        v1.5.0: Performance monitoring for Klipper G-code queue impact.
        """
        if len(self._perf_console_send_times) < 2:
            return 0.0

        now = time.time()
        # Filter to last 60 seconds
        recent = [t for t in self._perf_console_send_times if (now - t) <= 60.0]

        if len(recent) < 2:
            return 0.0

        time_span = recent[-1] - recent[0]
        if time_span <= 0:
            return 0.0

        # sends per second × 60 = sends per minute
        return (len(recent) - 1) / time_span * 60.0

    def _get_http_requests_per_second(self) -> float:
        """Calculate total HTTP request rate from all ProxyDrivers.

        Returns requests per second averaged since animation loop started.
        v1.5.0: Performance monitoring for network overhead.
        """
        total_requests = 0
        for driver in self.drivers.values():
            if isinstance(driver, ProxyDriver):
                total_requests += driver.total_requests

        # Calculate uptime from animation start time (not rolling frame window!)
        if self._perf_animation_start_time is None:
            return 0.0

        uptime = time.time() - self._perf_animation_start_time
        if uptime <= 0:
            return 0.0

        return total_requests / uptime

    def _get_cpu_percent(self) -> float:
        """Get Moonraker process CPU usage percentage (approximate).

        Uses /proc/self/stat to calculate average CPU usage since process started.
        Returns 0.0 if measurement fails.

        v1.5.0: Performance monitoring for resource usage.
        """
        try:
            # Read process stats from /proc/self/stat
            with open('/proc/self/stat', 'r') as f:
                stats = f.read().split()

            # Extract CPU time fields (utime + stime)
            # Field 14 = utime (user mode), Field 15 = stime (kernel mode)
            # Values are in clock ticks
            utime = int(stats[13])  # 0-indexed: field 14 is index 13
            stime = int(stats[14])  # 0-indexed: field 15 is index 14
            total_time = utime + stime

            # Get system clock ticks per second
            clock_ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])

            # Calculate elapsed wall time since process started
            # Field 22 = starttime (in clock ticks since boot)
            starttime = int(stats[21])

            # Get system uptime
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])

            # Calculate process uptime
            process_uptime = uptime_seconds - (starttime / clock_ticks)

            if process_uptime <= 0:
                return 0.0

            # CPU% = (total_cpu_time / process_uptime) * 100
            # This gives average CPU usage since process started
            cpu_percent = (total_time / clock_ticks / process_uptime) * 100.0

            return min(cpu_percent, 100.0)  # Cap at 100%

        except (FileNotFoundError, ValueError, IndexError, KeyError):
            # Fallback: return 0.0 if /proc not available or parsing fails
            return 0.0

    def _get_memory_mb(self) -> float:
        """Get Moonraker process memory usage in MB (RSS - Resident Set Size).

        Returns memory in megabytes. Returns 0.0 if measurement fails.

        v1.5.0: Performance monitoring for resource usage.
        """
        try:
            # Read process status from /proc/self/status
            with open('/proc/self/status', 'r') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        # VmRSS is in kB, convert to MB
                        mem_kb = int(line.split()[1])
                        return mem_kb / 1024.0
            return 0.0
        except (FileNotFoundError, ValueError, IndexError):
            # Fallback: return 0.0 if /proc not available
            return 0.0

    # ─────────────────────────────────────────────────────────────
    # API Endpoints
    # ─────────────────────────────────────────────────────────────
    
    async def _handle_status(self, web_request: WebRequest) -> Dict[str, Any]:
        # v1.5.0: Add ProxyDriver health status (ProxyDriver imported at module level)
        driver_health = {}
        for group_name, driver in self.drivers.items():
            if isinstance(driver, ProxyDriver):
                driver_health[group_name] = driver.get_health_status()

        return {
            "version": __version__,
            "klippy_ready": self.klippy_ready,
            "detector": self.state_detector.status(),
            "printer": {
                "klipper_state": self.printer_state.klipper_state,
                "print_state": self.printer_state.print_state,
                "progress": self.printer_state.progress,
                "bed_temp": self.printer_state.bed_temp,
                "bed_target": self.printer_state.bed_target,
                "extruder_temp": self.printer_state.extruder_temp,
                "extruder_target": self.printer_state.extruder_target,
                # v1.3.0 - Chamber temperature
                "chamber_temp": self.printer_state.chamber_temp,
                "chamber_target": self.printer_state.chamber_target,
                # v1.3.0 - Filament sensor (None if not installed)
                "filament_detected": self.printer_state.filament_detected,
                "position": {
                    "x": round(self.printer_state.position_x, 2),
                    "y": round(self.printer_state.position_y, 2),
                    "z": round(self.printer_state.position_z, 2),
                },
            },
            "config": {
                "max_brightness": self.max_brightness,
                "update_rate": self.update_rate,
                "update_rate_printing": self.update_rate_printing,
                "gpio_fps": self.gpio_fps,
                "debug": "console" if self.debug_console else self.debug,
            },
            "animation": {
                "running": self._animation_running,
                "fps": round(self._get_current_fps(), 2) if self._get_current_fps() is not None else None,
                "effects": {n: s.effect for n, s in self.effect_states.items()},
            },
            "led_groups": list(self.led_groups.keys()),
            "warnings": self.config_warnings,
            # v1.5.0: ProxyDriver health status
            "driver_health": driver_health if driver_health else None,
            # v1.5.0: Performance metrics
            "performance": {
                "fps": round(self._get_current_fps(), 2) if self._get_current_fps() is not None else None,
                "max_frame_time_ms": round(self._perf_max_frame_time, 2),
                "http_requests_per_second": round(self._get_http_requests_per_second(), 2),
                "console_sends_per_minute": round(self._get_console_sends_per_minute(), 1),
                "total_console_sends": self._perf_console_sends,
                # v1.5.0: Process resource usage
                "cpu_percent": round(self._get_cpu_percent(), 1),
                "memory_mb": round(self._get_memory_mb(), 1),
            },
        }
    
    async def _handle_colors(self, web_request: WebRequest) -> Dict[str, Any]:
        return {"colors": list_colors()}
    
    async def _handle_test_event(self, web_request: WebRequest) -> Dict[str, Any]:
        event_name = web_request.get_str("event", "idle")
        try:
            event = PrinterEvent(event_name)
            self.state_detector.force_event(event)
            await self._apply_event(event)
            return {"result": "ok", "event": event.value}
        except ValueError:
            return {"result": "error", "message": f"Unknown event: {event_name}"}
    
    async def _handle_reload(self, web_request: WebRequest) -> Dict[str, Any]:
        """Reload lumen.cfg without restarting Moonraker."""
        self._log_info("Reloading configuration...")
        
        # Stop animation loop
        if self._animation_running:
            self._animation_running = False
            if self._animation_task:
                self._animation_task.cancel()
                try:
                    await self._animation_task
                except asyncio.CancelledError:
                    pass
        
        # Reload config
        self._load_config()
        self._create_drivers()

        # Clear caches to prevent memory leaks
        self.effect_instances.clear()
        self._last_thermal_log.clear()
        self._driver_intervals.clear()

        # Recreate effect states for new drivers
        self.effect_states.clear()
        for name in self.drivers:
            self.effect_states[name] = EffectState()

        # v1.5.0: Rebuild driver interval cache after reload
        self._cache_driver_intervals()
        
        # Re-apply current event (this also restarts animation loop)
        current_event = self.state_detector.current_event
        await self._apply_event(current_event)
        
        result = {
            "result": "ok",
            "groups": list(self.led_groups.keys()),
            "events": list(self.event_mappings.keys()),
            "current_event": current_event.value,
        }
        
        if self.config_warnings:
            result["warnings"] = self.config_warnings

        return result

    async def _handle_effects(self, web_request: WebRequest) -> Dict[str, Any]:
        """
        GET /server/lumen/effects - List all available effects and their parameters (v1.6.5).

        Returns comprehensive information about each effect including:
        - Effect name and description
        - Configurable parameters and their defaults
        - Valid parameter ranges
        - Example usage
        """
        effects_info = {}

        for effect_name in sorted(EFFECT_REGISTRY.keys()):
            effect_class = EFFECT_REGISTRY[effect_name]
            effect_instance = effect_class()

            # Get effect defaults from effect_settings
            effect_params = self.effect_settings.get(effect_name, {})

            # Build parameter info
            info = {
                "name": effect_name,
                "description": effect_instance.description if hasattr(effect_instance, 'description') else f"{effect_name.title()} effect",
                "requires_led_count": effect_instance.requires_led_count,
                "requires_state_data": effect_instance.requires_state_data,
                "parameters": {},
            }

            # Add common parameters
            if effect_name not in ['off']:
                info["parameters"]["speed"] = {
                    "type": "float",
                    "default": float(effect_params.get("speed", 1.0)),
                    "min": 0.01,
                    "description": "Animation speed"
                }
                info["parameters"]["min_brightness"] = {
                    "type": "float",
                    "default": float(effect_params.get("min_brightness", 0.2)),
                    "min": 0.0,
                    "max": 1.0,
                    "description": "Minimum brightness"
                }
                info["parameters"]["max_brightness"] = {
                    "type": "float",
                    "default": float(effect_params.get("max_brightness", 1.0)),
                    "min": 0.0,
                    "max": 1.0,
                    "description": "Maximum brightness"
                }

            # Effect-specific parameters
            if effect_name == "disco":
                info["parameters"]["min_sparkle"] = {
                    "type": "int",
                    "default": int(effect_params.get("min_sparkle", 1)),
                    "min": 0,
                    "description": "Minimum LEDs lit per update"
                }
                info["parameters"]["max_sparkle"] = {
                    "type": "int",
                    "default": int(effect_params.get("max_sparkle", 6)),
                    "min": 1,
                    "description": "Maximum LEDs lit per update"
                }

            elif effect_name == "rainbow":
                info["parameters"]["rainbow_spread"] = {
                    "type": "float",
                    "default": float(effect_params.get("rainbow_spread", 1.0)),
                    "min": 0.0,
                    "max": 1.0,
                    "description": "Spectrum spread across strip"
                }

            elif effect_name == "fire":
                info["parameters"]["fire_cooling"] = {
                    "type": "float",
                    "default": float(effect_params.get("fire_cooling", 0.4)),
                    "min": 0.0,
                    "max": 1.0,
                    "description": "Cooling rate (higher = more chaotic)"
                }

            elif effect_name == "comet":
                info["parameters"]["comet_tail_length"] = {
                    "type": "int",
                    "default": int(effect_params.get("comet_tail_length", 4)),
                    "min": 1,
                    "description": "Length of trailing tail (LEDs)"
                }
                info["parameters"]["comet_fade_rate"] = {
                    "type": "float",
                    "default": float(effect_params.get("comet_fade_rate", 0.9)),
                    "min": 0.0,
                    "max": 1.0,
                    "description": "How quickly tail fades"
                }

            elif effect_name == "chase":
                info["parameters"]["chase_size"] = {
                    "type": "int",
                    "default": int(effect_params.get("chase_size", 2)),
                    "min": 1,
                    "description": "LEDs per chase segment"
                }
                info["parameters"]["chase_color_1"] = {
                    "type": "color",
                    "default": effect_params.get("chase_color_1", "lava"),
                    "description": "Predator color"
                }
                info["parameters"]["chase_color_2"] = {
                    "type": "color",
                    "default": effect_params.get("chase_color_2", "ice"),
                    "description": "Prey color"
                }

            elif effect_name == "kitt":
                info["parameters"]["kitt_eye_size"] = {
                    "type": "int",
                    "default": int(effect_params.get("kitt_eye_size", 3)),
                    "min": 1,
                    "description": "LEDs in bright center eye"
                }
                info["parameters"]["kitt_tail_length"] = {
                    "type": "int",
                    "default": int(effect_params.get("kitt_tail_length", 2)),
                    "min": 0,
                    "description": "Fading LEDs on each side"
                }
                info["parameters"]["base_color"] = {
                    "type": "color",
                    "default": effect_params.get("base_color", "red"),
                    "description": "Scanner color"
                }

            elif effect_name in ["thermal", "progress"]:
                info["parameters"]["gradient_curve"] = {
                    "type": "float",
                    "default": float(effect_params.get("gradient_curve", 1.0)),
                    "min": 0.1,
                    "description": "Gradient curve (1.0=linear, >1=sharp at end)"
                }

            effects_info[effect_name] = info

        return {
            "effects": effects_info,
            "count": len(effects_info)
        }

    async def _handle_set_group(self, web_request: WebRequest) -> Dict[str, Any]:
        """
        POST /server/lumen/set_group - Temporarily override a group's effect via API (v1.6.5).

        Parameters:
            group: Group name (required)
            effect: Effect name (required)
            color: Color name (optional, for effects that use color)
            duration: Override duration in seconds (optional, 0 = permanent until next state change)

        Examples:
            POST /server/lumen/set_group?group=left&effect=solid&color=red
            POST /server/lumen/set_group?group=left&effect=pulse&color=blue&duration=10
        """
        group_name = web_request.get_str("group", "")
        effect_name = web_request.get_str("effect", "")
        color_name = web_request.get_str("color", None)
        duration = web_request.get_float("duration", 0.0)

        # Validate group exists
        if not group_name or group_name not in self.drivers:
            return {
                "result": "error",
                "message": f"Unknown group '{group_name}'. Available groups: {', '.join(sorted(self.drivers.keys()))}"
            }

        # Validate effect exists
        if effect_name not in EFFECT_REGISTRY:
            return {
                "result": "error",
                "message": f"Unknown effect '{effect_name}'. Use /server/lumen/effects for list of valid effects."
            }

        # Validate color if provided
        base_color = (1.0, 1.0, 1.0)  # Default white
        if color_name:
            try:
                base_color = get_color(color_name)
            except ValueError:
                return {
                    "result": "error",
                    "message": f"Unknown color '{color_name}'. Use /server/lumen/colors for list of valid colors."
                }

        # Apply effect override
        driver = self.drivers[group_name]
        state = self.effect_states.get(group_name, EffectState())

        # Update state with override
        state.effect = effect_name
        state.base_color = base_color
        self.effect_states[group_name] = state

        # Apply the effect immediately
        await self._apply_effect(group_name, effect_name, state.base_color, driver)

        # If duration specified, schedule revert to current event mapping
        if duration > 0:
            async def _revert_override():
                await asyncio.sleep(duration)
                current_event = self.state_detector.current_event
                await self._apply_event(current_event)
                self._log_debug(f"Group '{group_name}' override expired, reverted to {current_event.value}")

            asyncio.create_task(_revert_override())

            return {
                "result": "ok",
                "group": group_name,
                "effect": effect_name,
                "color": color_name,
                "duration": duration,
                "message": f"Override applied for {duration}s"
            }
        else:
            return {
                "result": "ok",
                "group": group_name,
                "effect": effect_name,
                "color": color_name,
                "message": "Override applied until next state change"
            }

    # ======================
    # v1.7.0 - Test Mode API Handlers
    # ======================

    async def _handle_test_start(self, web_request: WebRequest) -> Dict[str, Any]:
        """
        POST /server/lumen/test/start - Enter test mode (v1.7.0).

        Test mode allows cycling through states and effects for debugging.
        Normal state detection is disabled while in test mode.
        """
        self._test_mode_enabled = True
        self._test_mode_state_index = 0
        self._test_mode_effect_index = 0
        # Default to first group for effect testing
        self._test_mode_group = sorted(self.drivers.keys())[0] if self.drivers else ""

        # Apply first test state
        if self._test_mode_states:
            test_state = self._test_mode_states[0]
            event = PrinterEvent(test_state)
            await self._apply_event(event)

            self._log_info(f"Test mode enabled - State: {test_state}")

            return {
                "result": "ok",
                "test_mode": "enabled",
                "current_state": test_state,
                "state_index": 0,
                "total_states": len(self._test_mode_states),
                "available_states": self._test_mode_states,
                "message": "Test mode enabled. Use next_state/prev_state to cycle states."
            }
        else:
            return {
                "result": "error",
                "message": "No states available for testing"
            }

    async def _handle_test_stop(self, web_request: WebRequest) -> Dict[str, Any]:
        """
        POST /server/lumen/test/stop - Exit test mode and reload config (v1.7.0).

        Disables test mode and returns to normal state detection.
        """
        self._test_mode_enabled = False

        # Reload config to return to normal operation
        self._load_config()

        # Apply current detected state
        current_event = self.state_detector.current_event
        await self._apply_event(current_event)

        self._log_info("Test mode disabled - returned to normal operation")

        return {
            "result": "ok",
            "test_mode": "disabled",
            "current_state": current_event.value,
            "message": "Test mode disabled, config reloaded"
        }

    async def _handle_test_next_state(self, web_request: WebRequest) -> Dict[str, Any]:
        """
        POST /server/lumen/test/next_state - Cycle to next printer state (v1.7.0).

        Only works when test mode is enabled.
        """
        if not self._test_mode_enabled:
            return {
                "result": "error",
                "message": "Test mode not enabled. Use /server/lumen/test/start first."
            }

        # Cycle to next state
        self._test_mode_state_index = (self._test_mode_state_index + 1) % len(self._test_mode_states)
        test_state = self._test_mode_states[self._test_mode_state_index]
        event = PrinterEvent(test_state)
        await self._apply_event(event)

        self._log_info(f"Test mode - State: {test_state} ({self._test_mode_state_index + 1}/{len(self._test_mode_states)})")

        return {
            "result": "ok",
            "current_state": test_state,
            "state_index": self._test_mode_state_index,
            "total_states": len(self._test_mode_states),
            "message": f"Switched to state: {test_state}"
        }

    async def _handle_test_prev_state(self, web_request: WebRequest) -> Dict[str, Any]:
        """
        POST /server/lumen/test/prev_state - Cycle to previous printer state (v1.7.0).

        Only works when test mode is enabled.
        """
        if not self._test_mode_enabled:
            return {
                "result": "error",
                "message": "Test mode not enabled. Use /server/lumen/test/start first."
            }

        # Cycle to previous state
        self._test_mode_state_index = (self._test_mode_state_index - 1) % len(self._test_mode_states)
        test_state = self._test_mode_states[self._test_mode_state_index]
        event = PrinterEvent(test_state)
        await self._apply_event(event)

        self._log_info(f"Test mode - State: {test_state} ({self._test_mode_state_index + 1}/{len(self._test_mode_states)})")

        return {
            "result": "ok",
            "current_state": test_state,
            "state_index": self._test_mode_state_index,
            "total_states": len(self._test_mode_states),
            "message": f"Switched to state: {test_state}"
        }

    async def _handle_test_next_effect(self, web_request: WebRequest) -> Dict[str, Any]:
        """
        POST /server/lumen/test/next_effect - Cycle to next effect on test group (v1.7.0).

        Parameters:
            group: Group name (optional, uses first group if not specified)

        Only works when test mode is enabled.
        """
        if not self._test_mode_enabled:
            return {
                "result": "error",
                "message": "Test mode not enabled. Use /server/lumen/test/start first."
            }

        # Allow changing test group
        group_name = web_request.get_str("group", self._test_mode_group)
        if group_name not in self.drivers:
            return {
                "result": "error",
                "message": f"Unknown group '{group_name}'. Available groups: {', '.join(sorted(self.drivers.keys()))}"
            }
        self._test_mode_group = group_name

        # Cycle to next effect
        self._test_mode_effect_index = (self._test_mode_effect_index + 1) % len(self._test_mode_effects)
        effect_name = self._test_mode_effects[self._test_mode_effect_index]

        # Apply effect to test group
        driver = self.drivers[group_name]
        state = self.effect_states.get(group_name, EffectState())
        state.effect = effect_name
        self.effect_states[group_name] = state
        await self._apply_effect(group_name, effect_name, state.base_color, driver)

        self._log_info(f"Test mode - Effect: {effect_name} on {group_name} ({self._test_mode_effect_index + 1}/{len(self._test_mode_effects)})")

        return {
            "result": "ok",
            "current_effect": effect_name,
            "effect_index": self._test_mode_effect_index,
            "total_effects": len(self._test_mode_effects),
            "group": group_name,
            "message": f"Switched to effect: {effect_name} on {group_name}"
        }

    async def _handle_test_prev_effect(self, web_request: WebRequest) -> Dict[str, Any]:
        """
        POST /server/lumen/test/prev_effect - Cycle to previous effect on test group (v1.7.0).

        Parameters:
            group: Group name (optional, uses current test group if not specified)

        Only works when test mode is enabled.
        """
        if not self._test_mode_enabled:
            return {
                "result": "error",
                "message": "Test mode not enabled. Use /server/lumen/test/start first."
            }

        # Allow changing test group
        group_name = web_request.get_str("group", self._test_mode_group)
        if group_name not in self.drivers:
            return {
                "result": "error",
                "message": f"Unknown group '{group_name}'. Available groups: {', '.join(sorted(self.drivers.keys()))}"
            }
        self._test_mode_group = group_name

        # Cycle to previous effect
        self._test_mode_effect_index = (self._test_mode_effect_index - 1) % len(self._test_mode_effects)
        effect_name = self._test_mode_effects[self._test_mode_effect_index]

        # Apply effect to test group
        driver = self.drivers[group_name]
        state = self.effect_states.get(group_name, EffectState())
        state.effect = effect_name
        self.effect_states[group_name] = state
        await self._apply_effect(group_name, effect_name, state.base_color, driver)

        self._log_info(f"Test mode - Effect: {effect_name} on {group_name} ({self._test_mode_effect_index + 1}/{len(self._test_mode_effects)})")

        return {
            "result": "ok",
            "current_effect": effect_name,
            "effect_index": self._test_mode_effect_index,
            "total_effects": len(self._test_mode_effects),
            "group": group_name,
            "message": f"Switched to effect: {effect_name} on {group_name}"
        }


def load_component(config: ConfigHelper) -> Lumen:
    return Lumen(config)
