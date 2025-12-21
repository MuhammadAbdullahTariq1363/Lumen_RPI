"""
Comet Effect - Moving light with trailing tail
"""

import math
from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState


class CometEffect(BaseEffect):
    """
    Comet effect - moving light with a trailing tail.

    Creates a comet/meteor effect with a bright head and fading tail moving
    across the LED strip. The comet wraps around when it reaches the end.

    Parameters (from EffectState):
        - base_color: Color of the comet
        - speed: Movement speed (LEDs per second)
        - max_brightness: Brightness of comet head
        - comet_tail_length: Length of trailing tail (in LEDs)
        - comet_fade_rate: How quickly tail fades (0.0-1.0, higher = shorter tail)
        - direction: "standard" (forward) or "reverse" (backward)
    """

    name = "comet"
    description = "Moving light with trailing tail"
    requires_led_count = True

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate comet position and colors."""
        if led_count <= 1:
            # Single LED: just show solid color
            return [state.base_color], True

        elapsed = now - state.start_time

        # Calculate position (0.0 to led_count)
        # speed is in LEDs per second
        position = (elapsed * state.speed) % led_count

        if state.direction == "reverse":
            position = led_count - position

        colors: List[Optional[RGB]] = []

        for i in range(led_count):
            # Calculate distance from comet head
            distance = self._circular_distance(i, position, led_count)

            if distance == 0:
                # Comet head - full brightness
                brightness = state.max_brightness
            elif distance <= state.comet_tail_length:
                # Tail - exponential fade
                fade_factor = 1.0 - (distance / state.comet_tail_length)
                # Apply fade rate for steeper or gentler falloff
                fade_factor = math.pow(fade_factor, 1.0 + state.comet_fade_rate * 2.0)
                brightness = state.max_brightness * fade_factor
            else:
                # Beyond tail - off
                colors.append(None)
                continue

            # Apply brightness to base color
            r, g, b = state.base_color
            colors.append((r * brightness, g * brightness, b * brightness))

        return colors, True

    @staticmethod
    def _circular_distance(led_index: int, position: float, led_count: int) -> float:
        """
        Calculate distance from LED to comet head, accounting for wrap-around.

        For forward-moving comet, we look behind the head position.
        Distance is how many LEDs behind the head this LED is.

        Args:
            led_index: LED position (0 to led_count-1)
            position: Comet head position (0.0 to led_count)
            led_count: Total number of LEDs

        Returns:
            Distance in LEDs (0.0 = at head, >0 = behind head)
        """
        # How far behind the head is this LED?
        distance = position - led_index

        # If negative, wrap around
        if distance < 0:
            distance += led_count

        # If we're ahead of the comet, we're not in the tail
        if distance > led_count / 2:
            return led_count  # Return large number to indicate "not in tail"

        return distance
