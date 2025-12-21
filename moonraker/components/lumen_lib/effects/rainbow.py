"""
Rainbow Effect - Cycling rainbow animation
"""

import math
from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState


class RainbowEffect(BaseEffect):
    """
    Rainbow effect - smooth cycling through the entire color spectrum.

    Creates a flowing rainbow pattern by cycling through HSV hue values.
    For multi-LED strips, the rainbow spreads across LEDs with each LED
    offset in hue. For single LEDs, all LEDs show the same cycling color.

    Parameters (from EffectState):
        - speed: Cycles per second (1.0 = full rainbow cycle per second)
        - max_brightness: Maximum brightness (0.0-1.0)
        - rainbow_spread: For multi-LED: hue offset between adjacent LEDs
                         (0.0-1.0, where 1.0 = full rainbow across strip)
    """

    name = "rainbow"
    description = "Cycling rainbow animation"
    requires_led_count = True  # Needs to know strip length for spreading

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate rainbow colors."""
        elapsed = now - state.start_time

        # Base hue rotates over time (0.0 to 1.0)
        base_hue = (elapsed * state.speed) % 1.0

        colors: List[Optional[RGB]] = []

        for i in range(led_count):
            # Calculate hue for this LED
            if led_count > 1:
                # Spread rainbow across strip
                hue_offset = (i / led_count) * state.rainbow_spread
            else:
                # Single LED: no offset
                hue_offset = 0.0

            hue = (base_hue + hue_offset) % 1.0

            # Convert HSV to RGB (S=1.0, V=max_brightness)
            rgb = self._hsv_to_rgb(hue, 1.0, state.max_brightness)
            colors.append(rgb)

        return colors, True

    @staticmethod
    def _hsv_to_rgb(h: float, s: float, v: float) -> RGB:
        """
        Convert HSV to RGB.

        Args:
            h: Hue (0.0-1.0)
            s: Saturation (0.0-1.0)
            v: Value/brightness (0.0-1.0)

        Returns:
            RGB tuple (0.0-1.0 per channel)
        """
        h = h * 6.0  # Scale hue to 0-6
        c = v * s    # Chroma
        x = c * (1 - abs(h % 2 - 1))

        if h < 1:
            r, g, b = c, x, 0
        elif h < 2:
            r, g, b = x, c, 0
        elif h < 3:
            r, g, b = 0, c, x
        elif h < 4:
            r, g, b = 0, x, c
        elif h < 5:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        return (r, g, b)
