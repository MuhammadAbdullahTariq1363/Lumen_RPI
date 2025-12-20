"""
Disco Effect - Random rainbow sparkles
"""

import random
from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
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

        min_lit = min(state.min_sparkle, led_count)
        max_lit = min(state.max_sparkle, led_count)
        num_lit = random.randint(min_lit, max_lit)

        all_indices = list(range(led_count))
        random.shuffle(all_indices)
        lit_indices = set(all_indices[:num_lit])

        colors: List[Optional[RGB]] = []
        for i in range(led_count):
            if i in lit_indices:
                # Generate random HSV color
                hue = random.random()
                h = hue * 6
                c = state.max_brightness
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
                colors.append((r, g, b))
            else:
                colors.append(None)  # LED off

        return colors, True
