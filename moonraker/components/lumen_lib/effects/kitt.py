"""
KITT Effect - Knight Rider scanner with optional toolhead tracking
"""

import math
from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState


class KITTEffect(BaseEffect):
    """
    KITT/Cylon scanner effect - bouncing light bar with fading trails.

    Classic Knight Rider / Battlestar Galactica Cylon eye effect with a
    bright center "eye" and exponentially fading trails on both sides.

    Two modes:
    1. Standard: Bounces back and forth at configured speed
    2. Tracking: Follows toolhead X or Y position (for bed meshing visualization)
       - When toolhead moves: scanner position tracks toolhead
       - When toolhead stopped: scanner resumes bouncing

    Parameters (from EffectState):
        - base_color: Scanner color (classic red or user choice)
        - speed: Bounce speed in sweeps per second
        - kitt_eye_size: Number of LEDs in bright center
        - kitt_tail_length: Fading LEDs on each side of eye
        - kitt_tracking_axis: "none" | "x" | "y" (default "none")
        - max_brightness: Brightness of center eye
    """

    name = "kitt"
    description = "Knight Rider scanner with optional tracking"
    requires_led_count = True
    requires_state_data = True  # Needs toolhead position for tracking mode

    def __init__(self):
        super().__init__()
        # Track bounce direction (1 = forward, -1 = backward)
        self._direction = 1
        # Remember last toolhead position for motion detection
        self._last_toolhead_pos = None

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate KITT scanner position and colors."""
        if led_count <= 1:
            # Single LED: just pulse
            return [state.base_color], True

        # Determine scanner position based on mode
        if state.kitt_tracking_axis != "none" and state_data:
            position = self._calculate_tracking_position(
                state, now, led_count, state_data
            )
        else:
            position = self._calculate_bounce_position(
                state, now, led_count
            )

        # Render scanner at position
        colors = self._render_scanner(
            position, led_count, state
        )

        return colors, True

    def _calculate_bounce_position(
        self,
        state: EffectState,
        now: float,
        led_count: int
    ) -> float:
        """Calculate bouncing scanner position."""
        elapsed = now - state.start_time

        # Calculate position using triangle wave (bounces at ends)
        # Speed is in full sweeps (left-to-right-to-left) per second
        cycle_time = 1.0 / state.speed  # Time for one complete cycle
        half_cycle = cycle_time / 2.0   # Time for one direction

        # Which half-cycle are we in?
        phase = (elapsed % cycle_time) / half_cycle

        if phase < 1.0:
            # Moving forward (0 to led_count-1)
            position = phase * (led_count - 1)
        else:
            # Moving backward (led_count-1 to 0)
            position = (2.0 - phase) * (led_count - 1)

        return position

    def _calculate_tracking_position(
        self,
        state: EffectState,
        now: float,
        led_count: int,
        state_data: dict
    ) -> float:
        """Calculate scanner position based on toolhead tracking."""
        # Get toolhead position from state_data
        toolhead_pos_x = state_data.get('toolhead_pos_x', 0.0)
        toolhead_pos_y = state_data.get('toolhead_pos_y', 0.0)
        bed_x_min = state_data.get('bed_x_min', 0.0)
        bed_x_max = state_data.get('bed_x_max', 300.0)
        bed_y_min = state_data.get('bed_y_min', 0.0)
        bed_y_max = state_data.get('bed_y_max', 300.0)

        # Determine which axis to track
        if state.kitt_tracking_axis == "x":
            current_pos = toolhead_pos_x
            min_pos = bed_x_min
            max_pos = bed_x_max
        elif state.kitt_tracking_axis == "y":
            current_pos = toolhead_pos_y
            min_pos = bed_y_min
            max_pos = bed_y_max
        else:
            # Fallback to bounce mode
            return self._calculate_bounce_position(state, now, led_count)

        # Check if toolhead is moving
        is_moving = False
        if self._last_toolhead_pos is not None:
            # Movement threshold: 1mm
            if abs(current_pos - self._last_toolhead_pos) > 1.0:
                is_moving = True

        self._last_toolhead_pos = current_pos

        if is_moving:
            # Map toolhead position to LED position
            # Normalize to 0.0-1.0
            normalized = (current_pos - min_pos) / max(1.0, max_pos - min_pos)
            normalized = max(0.0, min(1.0, normalized))  # Clamp

            # Map to LED index
            position = normalized * (led_count - 1)
        else:
            # Toolhead not moving - resume bouncing
            position = self._calculate_bounce_position(state, now, led_count)

        return position

    def _render_scanner(
        self,
        position: float,
        led_count: int,
        state: EffectState
    ) -> List[Optional[RGB]]:
        """
        Render KITT scanner at given position.

        Creates bright center eye with exponentially fading trails.
        """
        colors: List[Optional[RGB]] = []

        eye_center = int(position)
        eye_half_size = state.kitt_eye_size // 2

        for i in range(led_count):
            # Distance from scanner center
            distance = abs(i - position)

            # Check if in bright center eye
            if distance <= eye_half_size:
                # Full brightness
                brightness = state.max_brightness
            elif distance <= eye_half_size + state.kitt_tail_length:
                # Fading tail - exponential falloff
                tail_distance = distance - eye_half_size
                fade_factor = 1.0 - (tail_distance / state.kitt_tail_length)
                # Exponential curve for sharper falloff
                fade_factor = math.pow(fade_factor, 2.5)
                brightness = state.max_brightness * fade_factor
            else:
                # Beyond tail - off
                colors.append(None)
                continue

            # Apply brightness to base color
            r, g, b = state.base_color
            colors.append((r * brightness, g * brightness, b * brightness))

        return colors
