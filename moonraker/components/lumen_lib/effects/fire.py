"""
Fire Effect - Flickering flame simulation
"""

import random
import math
from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState


class FireEffect(BaseEffect):
    """
    Fire effect - realistic flickering flame simulation.

    Creates a flickering orange/red/yellow flame effect by randomizing brightness
    and hue within the fire color spectrum. Each LED flickers independently to
    create a chaotic, organic flame appearance.

    Parameters (from EffectState):
        - speed: Flicker speed (updates per second, higher = more chaotic)
        - min_brightness: Minimum flame brightness (0.0-1.0)
        - max_brightness: Maximum flame brightness (0.0-1.0)
        - fire_cooling: How much flames cool between updates (0.0-1.0)
                       Higher values = more chaotic flickering
    """

    name = "fire"
    description = "Flickering flame simulation"
    requires_led_count = True

    def __init__(self):
        super().__init__()
        # Track per-LED heat values for smoother flickering
        self._heat_values: List[float] = []

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate fire flicker colors."""
        time_since_update = now - state.last_update
        interval = 1.0 / state.speed

        if time_since_update < interval:
            return [], False  # Not time to update yet

        # Initialize heat values if needed
        if len(self._heat_values) != led_count:
            self._heat_values = [0.5 for _ in range(led_count)]

        # Use microsecond precision for random seed
        random.seed(int(now * 1000000))

        colors: List[Optional[RGB]] = []

        for i in range(led_count):
            # Cool down the LED
            self._heat_values[i] *= (1.0 - state.fire_cooling)

            # Random chance to spark up
            if random.random() < 0.1:  # 10% chance per update
                self._heat_values[i] = min(1.0, self._heat_values[i] + random.uniform(0.2, 0.5))

            # Add small random fluctuation
            self._heat_values[i] += random.uniform(-0.05, 0.05)
            self._heat_values[i] = max(0.0, min(1.0, self._heat_values[i]))

            # Convert heat to fire color
            heat = self._heat_values[i]
            brightness = state.min_brightness + heat * (state.max_brightness - state.min_brightness)

            # Fire color spectrum: dark red -> orange -> yellow -> white
            # Heat maps to hue: 0.0 (red) -> 0.15 (yellow)
            hue = heat * 0.15  # 0-15 degrees (red-orange-yellow range)

            # Higher heat = more saturated (brighter flames)
            saturation = 1.0 - (heat * 0.3)  # Less saturation as heat increases

            rgb = self._hsv_to_rgb(hue, saturation, brightness)
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
        m = v - c

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

        return (r + m, g + m, b + m)
