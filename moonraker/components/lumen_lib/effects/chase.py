"""
Chase Effect - Two colored segments chasing each other
"""

import random
import math
from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState


class ChaseEffect(BaseEffect):
    """
    Chase effect - two colored segments chasing each other around the strip.

    Creates a dynamic chase pattern with two segments that vary their distance
    from each other during animation for visual interest.

    Multi-group support: When multiple groups use chase with numbering
    (e.g., "chase 1", "chase 2"), they coordinate to create a seamless
    animation across all strips.

    Parameters (from EffectState):
        - chase_color_1: Color of first segment
        - chase_color_2: Color of second segment
        - speed: Movement speed (LEDs per second)
        - chase_size: LEDs per segment
        - chase_offset_base: Base distance between segments (0.0-1.0 of strip length)
        - chase_offset_variation: How much offset varies (0.0-1.0)
        - max_brightness: Maximum brightness
    """

    name = "chase"
    description = "Two colored segments chasing each other"
    requires_led_count = True

    def __init__(self):
        super().__init__()
        # Track offset variation over time
        self._offset_phase = 0.0

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate chase segment positions and colors."""
        if led_count <= 1:
            # Single LED: just alternate colors
            elapsed = now - state.start_time
            phase = int(elapsed * state.speed) % 2
            return [state.chase_color_1 if phase == 0 else state.chase_color_2], True

        elapsed = now - state.start_time

        # Calculate first segment position (wraps around)
        position_1 = (elapsed * state.speed) % led_count

        # Calculate dynamic offset
        # Base offset + sinusoidal variation
        self._offset_phase = (elapsed * 0.5) % (2 * math.pi)  # Slow variation
        offset_variation = math.sin(self._offset_phase) * state.chase_offset_variation
        current_offset = state.chase_offset_base + offset_variation

        # Ensure offset stays in reasonable range (0.2 to 0.8 of strip length)
        current_offset = max(0.2, min(0.8, current_offset))

        # Second segment position
        position_2 = (position_1 + led_count * current_offset) % led_count

        colors: List[Optional[RGB]] = []

        for i in range(led_count):
            # Check if LED is in segment 1
            in_segment_1 = self._in_segment(i, position_1, state.chase_size, led_count)
            # Check if LED is in segment 2
            in_segment_2 = self._in_segment(i, position_2, state.chase_size, led_count)

            if in_segment_1:
                # Apply brightness to color 1
                r, g, b = state.chase_color_1
                colors.append((r * state.max_brightness, g * state.max_brightness, b * state.max_brightness))
            elif in_segment_2:
                # Apply brightness to color 2
                r, g, b = state.chase_color_2
                colors.append((r * state.max_brightness, g * state.max_brightness, b * state.max_brightness))
            else:
                # LED off
                colors.append(None)

        return colors, True

    @staticmethod
    def _in_segment(led_index: int, segment_position: float, segment_size: int, led_count: int) -> bool:
        """
        Check if LED is within a segment, handling wrap-around.

        Args:
            led_index: LED position (0 to led_count-1)
            segment_position: Center of segment (0.0 to led_count)
            segment_size: Number of LEDs in segment
            led_count: Total LEDs in strip

        Returns:
            True if LED is in segment
        """
        # Segment spans from (position - size/2) to (position + size/2)
        start = segment_position - segment_size / 2.0
        end = segment_position + segment_size / 2.0

        # Check if LED is in range, handling wrap-around
        if end <= led_count:
            # No wrap-around
            return start <= led_index < end
        else:
            # Wraps around end
            return led_index >= start or led_index < (end % led_count)
