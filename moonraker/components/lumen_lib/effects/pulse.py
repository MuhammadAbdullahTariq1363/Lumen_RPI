"""
Pulse Effect - Breathing animation
"""

import math
from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState


class PulseEffect(BaseEffect):
    """
    Pulse/breathing effect - smooth sine wave brightness modulation.

    Creates a gentle breathing pattern by varying LED brightness using a sine wave.
    The brightness oscillates between min_brightness and max_brightness at the
    specified speed (cycles per second).

    Parameters (from EffectState):
        - base_color: RGB color to pulse
        - speed: Cycles per second (1.0 = 1 second per cycle)
        - min_brightness: Minimum brightness (0.0-1.0)
        - max_brightness: Maximum brightness (0.0-1.0)
    """

    name = "pulse"
    description = "Breathing animation with smooth sine wave"

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate pulsing color."""
        elapsed = now - state.start_time
        phase = (math.sin(elapsed * state.speed * 2 * math.pi) + 1) / 2
        brightness = state.min_brightness + phase * (state.max_brightness - state.min_brightness)

        r, g, b = state.base_color
        return [(r * brightness, g * brightness, b * brightness)], True
