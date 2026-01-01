"""
LUMEN Drivers - LED hardware drivers

KlipperDriver: SET_LED for MCU-attached neopixels
PWMDriver: SET_PIN for non-addressable strips
GPIODriver: rpi_ws281x for Pi GPIO-attached neopixels
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .colors import RGB
import urllib.request
import urllib.error
import json

_logger = logging.getLogger(__name__)

# Timeout for gcode commands (seconds)
GCODE_TIMEOUT = 2.0

# Try to import rpi_ws281x (only available on Raspberry Pi)
try:
    from rpi_ws281x import PixelStrip, Color
    RPI_WS281X_AVAILABLE = True
except ImportError:
    RPI_WS281X_AVAILABLE = False
    PixelStrip = None
    Color = None

# Shared pixel strips by GPIO pin (multiple groups can share one strip)
# Thread-safe global state with locks (similar to ws281x_proxy.py)
from threading import Lock
_gpio_strips: Dict[int, "PixelStrip"] = {}
_gpio_strip_sizes: Dict[int, int] = {}
_gpio_strip_locks: Dict[int, Lock] = {}
_gpio_strip_locks_lock = Lock()  # Protect lock creation


class LEDDriver:
    """Base class for LED drivers."""
    
    def __init__(self, name: str, config: Dict[str, Any], server: Any):
        self.name = name
        self.config = config
        self.server = server
        self.led_count = 1
    
    async def set_color(self, r: float, g: float, b: float) -> None:
        """Set all LEDs to a solid color."""
        raise NotImplementedError
    
    async def set_off(self) -> None:
        """Turn off all LEDs."""
        await self.set_color(0.0, 0.0, 0.0)


class KlipperDriver(LEDDriver):
    """
    Driver for Klipper MCU-attached neopixels.
    Uses SET_LED gcode command via klippy_apis.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], server: Any):
        super().__init__(name, config, server)
        self.neopixel = config.get("neopixel", name)
        self.index_start = config.get("index_start", 1)
        self.index_end = config.get("index_end", self.index_start)
        self.led_count = self.index_end - self.index_start + 1
    
    async def set_color(self, r: float, g: float, b: float) -> None:
        """Set LEDs in this group's index range to a solid color."""
        try:
            klippy_apis = self.server.lookup_component("klippy_apis")

            # Set all LEDs except the last with TRANSMIT=0
            if self.led_count > 1:
                for i in range(self.index_start, self.index_end):  # This excludes index_end
                    gcode = f"SET_LED LED={self.neopixel} RED={r:.3f} GREEN={g:.3f} BLUE={b:.3f} INDEX={i} TRANSMIT=0"
                    await asyncio.wait_for(klippy_apis.run_gcode(gcode), timeout=GCODE_TIMEOUT)

            # Set the last LED with TRANSMIT=1 to flush all changes
            gcode = f"SET_LED LED={self.neopixel} RED={r:.3f} GREEN={g:.3f} BLUE={b:.3f} INDEX={self.index_end} TRANSMIT=1"
            await asyncio.wait_for(klippy_apis.run_gcode(gcode), timeout=GCODE_TIMEOUT)
        except asyncio.TimeoutError:
            _logger.warning(f"[LUMEN] {self.name} SET_LED timeout (Klipper busy)")
        except Exception as e:
            _logger.error(f"[LUMEN] {self.name} SET_LED failed: {e}")
    
    async def set_leds(self, colors: List[Optional[RGB]]) -> None:
        """Set individual LEDs to specific colors. None = off."""
        try:
            klippy_apis = self.server.lookup_component("klippy_apis")
            
            for i, color in enumerate(colors):
                led_index = self.index_start + i
                if led_index > self.index_end:
                    break
                
                is_last = (i == len(colors) - 1) or (led_index == self.index_end)
                transmit = 1 if is_last else 0
                
                if color is None:
                    r, g, b = 0.0, 0.0, 0.0
                else:
                    r, g, b = color
                
                gcode = f"SET_LED LED={self.neopixel} RED={r:.3f} GREEN={g:.3f} BLUE={b:.3f} INDEX={led_index} TRANSMIT={transmit}"
                await asyncio.wait_for(klippy_apis.run_gcode(gcode), timeout=GCODE_TIMEOUT)
        except asyncio.TimeoutError:
            _logger.warning(f"[LUMEN] {self.name} SET_LEDS timeout (Klipper busy)")
        except Exception as e:
            _logger.error(f"[LUMEN] {self.name} SET_LEDS failed: {e}")


class PWMDriver(LEDDriver):
    """
    Driver for simple PWM LED strips (brightness only, no color).
    Uses SET_PIN gcode command via klippy_apis.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], server: Any):
        super().__init__(name, config, server)
        self.pin_name = config.get("pin_name", name)
        self.scale = config.get("scale", 1.0)
    
    async def set_color(self, r: float, g: float, b: float) -> None:
        """Set brightness based on color intensity."""
        brightness = max(r, g, b)
        await self.set_brightness(brightness)
    
    async def set_brightness(self, value: float) -> None:
        """Set PWM brightness (0.0-1.0)."""
        try:
            klippy_apis = self.server.lookup_component("klippy_apis")
            scaled = value * self.scale
            gcode = f"SET_PIN PIN={self.pin_name} VALUE={scaled:.2f}"
            await asyncio.wait_for(klippy_apis.run_gcode(gcode), timeout=GCODE_TIMEOUT)
        except asyncio.TimeoutError:
            _logger.warning(f"[LUMEN] {self.name} SET_PIN timeout (Klipper busy)")
        except Exception as e:
            _logger.error(f"[LUMEN] {self.name} SET_PIN failed: {e}")
    
    async def set_off(self) -> None:
        await self.set_brightness(0.0)


class GPIODriver(LEDDriver):
    """
    Driver for Raspberry Pi GPIO-attached neopixels.
    Uses rpi_ws281x library for direct hardware control.
    
    Multiple groups can share the same GPIO pin with different index ranges.
    """
    
    # LED strip configuration (WS2812B defaults)
    LED_FREQ_HZ = 800000      # LED signal frequency in hertz
    LED_DMA = 10              # DMA channel for generating signal
    LED_INVERT = False        # True to invert the signal
    LED_BRIGHTNESS = 255      # Global brightness (0-255)
    LED_CHANNEL = 0           # GPIO 18 uses PWM channel 0
    
    def __init__(self, name: str, config: Dict[str, Any], server: Any):
        super().__init__(name, config, server)
        self.gpio_pin = int(config.get("gpio_pin", 18))
        self.index_start = config.get("index_start", 1)
        self.index_end = config.get("index_end", self.index_start)
        self.led_count = self.index_end - self.index_start + 1
        self.strip: Optional["PixelStrip"] = None
        
        if not RPI_WS281X_AVAILABLE:
            _logger.error(f"[LUMEN] {name}: rpi_ws281x not available (install with: pip install rpi_ws281x)")
            return
        
        # Get or create shared strip for this GPIO pin
        self._init_strip()
    
    def _init_strip(self) -> None:
        """Initialize or get shared PixelStrip for this GPIO pin."""
        global _gpio_strips, _gpio_strip_sizes, _gpio_strip_locks, _gpio_strip_locks_lock

        # Ensure per-pin lock exists (thread-safe lock creation)
        with _gpio_strip_locks_lock:
            if self.gpio_pin not in _gpio_strip_locks:
                _gpio_strip_locks[self.gpio_pin] = Lock()

        # All strip operations protected by pin-specific lock
        with _gpio_strip_locks[self.gpio_pin]:
            if self.gpio_pin in _gpio_strips:
                # Strip already exists - check if we need more LEDs
                current_size = _gpio_strip_sizes[self.gpio_pin]
                if self.index_end > current_size:
                    # Need to recreate strip with more LEDs
                    _logger.info(f"[LUMEN] Expanding GPIO {self.gpio_pin} strip from {current_size} to {self.index_end} LEDs")
                    old_strip = _gpio_strips[self.gpio_pin]

                    try:
                        # Create new strip with expanded size
                        new_strip = PixelStrip(
                            self.index_end,
                            self.gpio_pin,
                            self.LED_FREQ_HZ,
                            self.LED_DMA,
                            self.LED_INVERT,
                            self.LED_BRIGHTNESS,
                            self.LED_CHANNEL
                        )
                        new_strip.begin()

                        # Copy existing LED states from old strip
                        for i in range(current_size):
                            try:
                                color = old_strip.getPixelColor(i)
                                new_strip.setPixelColor(i, color)
                            except Exception as e:
                                # v1.4.0: Log exception for debugging
                                _logger.debug(f"[LUMEN] Failed to copy LED {i} state during strip expansion: {e}")

                        # Replace with new expanded strip
                        _gpio_strips[self.gpio_pin] = new_strip
                        _gpio_strip_sizes[self.gpio_pin] = self.index_end
                        self.strip = new_strip
                        _logger.info(f"[LUMEN] Successfully expanded GPIO {self.gpio_pin} strip to {self.index_end} LEDs")
                    except Exception as e:
                        _logger.error(f"[LUMEN] Failed to expand GPIO strip: {e}")
                        # Keep using old strip if expansion fails
                        self.strip = old_strip
                else:
                    self.strip = _gpio_strips[self.gpio_pin]
            else:
                # Create new strip
                total_leds = self.index_end  # index_end is the highest LED we need
                _logger.info(f"[LUMEN] Creating GPIO {self.gpio_pin} strip with {total_leds} LEDs")

                try:
                    self.strip = PixelStrip(
                        total_leds,
                        self.gpio_pin,
                        self.LED_FREQ_HZ,
                        self.LED_DMA,
                        self.LED_INVERT,
                        self.LED_BRIGHTNESS,
                        self.LED_CHANNEL
                    )
                    self.strip.begin()
                    _gpio_strips[self.gpio_pin] = self.strip
                    _gpio_strip_sizes[self.gpio_pin] = total_leds
                except Exception as e:
                    _logger.error(f"[LUMEN] Failed to initialize GPIO strip: {e}")
                self.strip = None
    
    def _rgb_to_color(self, r: float, g: float, b: float) -> int:
        """Convert 0.0-1.0 RGB to rpi_ws281x Color."""
        return Color(int(r * 255), int(g * 255), int(b * 255))
    
    async def set_color(self, r: float, g: float, b: float) -> None:
        """Set all LEDs in this group's range to a solid color."""
        if not self.strip:
            return
        
        color = self._rgb_to_color(r, g, b)
        for i in range(self.index_start - 1, self.index_end):  # Convert to 0-indexed
            self.strip.setPixelColor(i, color)
        self.strip.show()
    
    async def set_leds(self, colors: List[Optional[RGB]]) -> None:
        """Set individual LEDs to specific colors. None = off."""
        if not self.strip:
            return
        
        for i, color in enumerate(colors):
            led_index = self.index_start - 1 + i  # Convert to 0-indexed
            if led_index >= self.index_end:
                break
            
            if color is None:
                self.strip.setPixelColor(led_index, Color(0, 0, 0))
            else:
                r, g, b = color
                self.strip.setPixelColor(led_index, self._rgb_to_color(r, g, b))
        
        self.strip.show()
    
    async def set_off(self) -> None:
        """Turn off all LEDs in this group's range."""
        if not self.strip:
            return
        
        for i in range(self.index_start - 1, self.index_end):
            self.strip.setPixelColor(i, Color(0, 0, 0))
        self.strip.show()


class ProxyDriver(LEDDriver):
    """
    Driver communicating with a helper ws281x proxy server running as root.
    The proxy avoids needing Moonraker to run with raw IO privileges.

    v1.5.0: Added retry logic, health tracking, and better error handling.
    """
    def __init__(self, name: str, config: Dict[str, Any], server: Any):
        super().__init__(name, config, server)
        self.gpio_pin = int(config.get("gpio_pin", 18))
        self.index_start = int(config.get("index_start", 1))
        self.index_end = int(config.get("index_end", self.index_start))
        self.led_count = self.index_end - self.index_start + 1
        self.proxy_host = config.get("proxy_host", "127.0.0.1")
        self.proxy_port = int(config.get("proxy_port", 3769))
        # Color order for WS281x strips (most common is GRB for WS2812B)
        self.color_order = config.get("color_order", "GRB").upper().strip()

        # v1.5.0: Health tracking
        self.consecutive_failures = 0
        self.total_requests = 0
        self.total_failures = 0
        self.last_error: Optional[str] = None
        self.is_healthy = True

        # Note: Strip pre-initialization will happen on first use.
        # We can't create tasks in __init__ since we're not in an async context yet.

    def _proxy_url(self, path: str) -> str:
        return f"http://{self.proxy_host}:{self.proxy_port}{path}"

    async def _post(self, path: str, payload: Dict[str, Any]) -> bool:
        """
        Send POST request to proxy with retry logic and health tracking.

        v1.5.0: Added exponential backoff retry, health tracking, and better error handling.

        Args:
            path: API endpoint path
            payload: JSON payload

        Returns:
            True if successful, False if all retries failed
        """
        url = self._proxy_url(path)
        data = json.dumps(payload).encode('utf-8')
        self.total_requests += 1

        # v1.5.0: Stop trying if we've had too many consecutive failures (backpressure)
        if self.consecutive_failures >= 10:
            # Silent failure to prevent log spam
            return False

        max_retries = 3
        for attempt in range(max_retries):
            # Exponential backoff: 0s, 0.1s, 0.2s
            if attempt > 0:
                await asyncio.sleep(attempt * 0.1)

            def _send():
                try:
                    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                    # v1.5.0: Reduced timeout to 1.0s (was 2.0s)
                    with urllib.request.urlopen(req, timeout=1.0) as resp:
                        if resp.getcode() == 200:
                            return True, None
                except Exception as e:
                    return False, str(e)
                return False, "Unknown error"

            try:
                success, error = await asyncio.to_thread(_send)
                if success:
                    # v1.5.0: Success - reset failure counter and update health
                    if self.consecutive_failures > 0:
                        _logger.info(f"[LUMEN] ProxyDriver {self.name} recovered (was {self.consecutive_failures} failures)")
                    self.consecutive_failures = 0
                    self.is_healthy = True
                    return True
                else:
                    self.last_error = error
            except Exception as e:
                self.last_error = str(e)

        # v1.5.0: All retries failed - update health tracking
        self.total_failures += 1
        self.consecutive_failures += 1

        # Log warning on first failure or every 10th consecutive failure
        if self.consecutive_failures == 1 or self.consecutive_failures % 10 == 0:
            _logger.warning(
                f"[LUMEN] ProxyDriver {self.name} failed after {max_retries} retries: {self.last_error} "
                f"(consecutive failures: {self.consecutive_failures})"
            )

        # Mark as unhealthy after 5 consecutive failures
        if self.consecutive_failures >= 5:
            self.is_healthy = False

        return False

    async def set_color(self, r: float, g: float, b: float) -> None:
        payload = {
            "gpio_pin": self.gpio_pin,
            "index_start": self.index_start,
            "index_end": self.index_end,
            "r": r,
            "g": g,
            "b": b,
            "color_order": self.color_order,
        }
        await self._post('/set_color', payload)

    async def set_leds(self, colors: List[Optional[RGB]]) -> None:
        payload = {
            "gpio_pin": self.gpio_pin,
            "index_start": self.index_start,
            "colors": colors,
            "color_order": self.color_order,
        }
        await self._post('/set_leds', payload)

    async def set_off(self) -> None:
        await self.set_color(0.0, 0.0, 0.0)

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of proxy connection (v1.5.0).

        Returns:
            Dict with health metrics for debugging
        """
        return {
            "is_healthy": self.is_healthy,
            "consecutive_failures": self.consecutive_failures,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "success_rate": f"{100 * (1 - self.total_failures / max(1, self.total_requests)):.1f}%",
            "last_error": self.last_error,
        }

    @staticmethod
    async def batch_update(proxy_host: str, proxy_port: int, updates: List[Dict[str, Any]]) -> bool:
        """
        Send multiple LED updates in a single HTTP request (v1.5.0).

        Args:
            proxy_host: Proxy server hostname
            proxy_port: Proxy server port
            updates: List of update dictionaries, each containing:
                - type: 'set_color' or 'set_leds'
                - gpio_pin: GPIO pin number
                - index_start/index_end: LED indices
                - r, g, b: Color values (for set_color)
                - colors: List of RGB tuples (for set_leds)
                - color_order: Color order string

        Returns:
            True if successful, False otherwise

        Example:
            updates = [
                {'type': 'set_color', 'gpio_pin': 21, 'index_start': 1, 'index_end': 50,
                 'r': 1.0, 'g': 0.0, 'b': 0.0, 'color_order': 'GRB'},
                {'type': 'set_leds', 'gpio_pin': 21, 'index_start': 51,
                 'colors': [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], 'color_order': 'GRB'},
            ]
            await ProxyDriver.batch_update('127.0.0.1', 3769, updates)
        """
        url = f"http://{proxy_host}:{proxy_port}/batch_update"
        payload = {"updates": updates}
        data = json.dumps(payload).encode('utf-8')

        def _send():
            try:
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.getcode() == 200:
                        return True, None
            except Exception as e:
                return False, str(e)
            return False, "Unknown error"

        try:
            success, error = await asyncio.to_thread(_send)
            if not success:
                _logger.warning(f"[LUMEN] ProxyDriver batch_update failed: {error}")
            return success
        except Exception as e:
            _logger.warning(f"[LUMEN] ProxyDriver batch_update exception: {e}")
            return False


def create_driver(name: str, config: Dict[str, Any], server: Any) -> Optional[LEDDriver]:
    """Factory function to create the appropriate driver."""
    driver_type = config.get("driver", "klipper")
    
    if driver_type == "klipper":
        return KlipperDriver(name, config, server)
    elif driver_type == "pwm":
        return PWMDriver(name, config, server)
    elif driver_type == "gpio":
        if not RPI_WS281X_AVAILABLE:
            _logger.error(f"[LUMEN] GPIO driver requires rpi_ws281x (pip install rpi_ws281x)")
            return None
        return GPIODriver(name, config, server)
    elif driver_type == "proxy":
        return ProxyDriver(name, config, server)
    else:
        _logger.error(f"[LUMEN] Unknown driver type '{driver_type}' for {name}")
        return None
