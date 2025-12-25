"""
Rainbow Effect - Cycling rainbow animation
"""

import math
from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB, hsv_to_rgb
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

            # v1.4.0: Use shared HSV→RGB utility (eliminates duplication)
            rgb = hsv_to_rgb(hue, 1.0, state.max_brightness)
            colors.append(rgb)

        return colors, True
