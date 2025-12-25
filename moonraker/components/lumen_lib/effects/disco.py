"""
Disco Effect - Random rainbow sparkles
"""

import random
from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB, hsv_to_rgb
from ..effects import EffectState


class DiscoEffect(BaseEffect):
    """
    Disco/sparkle effect - random rainbow colors on randomly selected LEDs.

    Creates a dynamic party effect by randomly selecting a subset of LEDs and
    assigning them random HSV-generated colors. The number of lit LEDs varies
    between min_sparkle and max_sparkle each update.

    Parameters (from EffectState):
        - speed: Updates per second (higher = more chaotic)
        - min_sparkle: Minimum LEDs lit simultaneously
        - max_sparkle: Maximum LEDs lit simultaneously
        - max_brightness: Brightness cap for colors
    """

    name = "disco"
    description = "Random rainbow sparkles"
    requires_led_count = True  # Needs to know how many LEDs

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate disco sparkle colors."""
        time_since_update = now - state.last_update
        interval = 1.0 / state.speed

        if time_since_update < interval:
            return [], False  # Not time to update yet

        # Use microsecond precision for random seed to avoid pattern repetition
        # at slow update rates (< 1 Hz)
        random.seed(int(now * 1000000))

        # v1.4.0: Critical - Ensure min_lit <= max_lit to prevent ValueError
        min_lit = max(1, min(state.min_sparkle, led_count))
        max_lit = max(min_lit, min(state.max_sparkle, led_count))
        num_lit = random.randint(min_lit, max_lit)

        # v1.4.0: Optimized random selection - O(k) instead of O(n log n)
        lit_indices = set(random.sample(range(led_count), num_lit))

        colors: List[Optional[RGB]] = []
        for i in range(led_count):
            if i in lit_indices:
                # v1.4.0: Generate random rainbow color using shared HSV→RGB utility
                hue = random.random()
                rgb = hsv_to_rgb(hue, 1.0, state.max_brightness)
                colors.append(rgb)
            else:
                colors.append(None)  # LED off

        return colors, True
