"""
Heartbeat Effect - Double-pulse pattern
"""

from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState

# Heartbeat effect timing constants (percentages of cycle)
HEARTBEAT_FIRST_PULSE_DURATION = 0.15    # First pulse rise (15% of cycle)
HEARTBEAT_DIP_DURATION = 0.05            # Dip between pulses (5% of cycle)
HEARTBEAT_SECOND_PULSE_DURATION = 0.05   # Second pulse (5% of cycle)
HEARTBEAT_FADE_DURATION = 0.10           # Fade after second pulse (10% of cycle)
HEARTBEAT_SECOND_PULSE_INTENSITY = 0.5   # Second pulse is 50% of first


class HeartbeatEffect(BaseEffect):
    """
    Heartbeat effect - double-pulse pattern mimicking a real heartbeat.

    Creates a realistic heartbeat pattern with two quick pulses followed by a
    longer rest period. The pattern consists of:
    - First pulse (15% of cycle): rise to max brightness
    - Brief dip (5%): drop to 50% intensity
    - Second pulse (5%): rise back to max
    - Fade out (10%): gradual return to min brightness
    - Rest (remaining 65%): stays at min brightness

    Parameters (from EffectState):
        - base_color: RGB color to pulse
        - speed: Beats per second (1.2 = 72 BPM, resting heart rate)
        - min_brightness: Minimum brightness during rest
        - max_brightness: Maximum brightness during pulses
    """

    name = "heartbeat"
    description = "Double-pulse heartbeat pattern"

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate heartbeat pulsing color."""
        elapsed = now - state.start_time
        cycle_time = 1.0 / state.speed
        phase = (elapsed % cycle_time) / cycle_time

        if phase < HEARTBEAT_FIRST_PULSE_DURATION:
            # First pulse rising
            t = phase / HEARTBEAT_FIRST_PULSE_DURATION
            brightness = state.min_brightness + t * (state.max_brightness - state.min_brightness)
        elif phase < HEARTBEAT_FIRST_PULSE_DURATION + HEARTBEAT_DIP_DURATION:
            # Dip between pulses
            t = (phase - HEARTBEAT_FIRST_PULSE_DURATION) / HEARTBEAT_DIP_DURATION
            brightness = state.max_brightness - t * (state.max_brightness - state.min_brightness) * HEARTBEAT_SECOND_PULSE_INTENSITY
        elif phase < HEARTBEAT_FIRST_PULSE_DURATION + HEARTBEAT_DIP_DURATION + HEARTBEAT_SECOND_PULSE_DURATION:
            # Second pulse rising
            t = (phase - HEARTBEAT_FIRST_PULSE_DURATION - HEARTBEAT_DIP_DURATION) / HEARTBEAT_SECOND_PULSE_DURATION
            brightness = state.min_brightness + HEARTBEAT_SECOND_PULSE_INTENSITY + t * (state.max_brightness - state.min_brightness) * HEARTBEAT_SECOND_PULSE_INTENSITY
        elif phase < HEARTBEAT_FIRST_PULSE_DURATION + HEARTBEAT_DIP_DURATION + HEARTBEAT_SECOND_PULSE_DURATION + HEARTBEAT_FADE_DURATION:
            # Fade out after second pulse
            t = (phase - HEARTBEAT_FIRST_PULSE_DURATION - HEARTBEAT_DIP_DURATION - HEARTBEAT_SECOND_PULSE_DURATION) / HEARTBEAT_FADE_DURATION
            brightness = state.max_brightness - t * (state.max_brightness - state.min_brightness)
        else:
            # Rest period
            brightness = state.min_brightness

        r, g, b = state.base_color
        return [(r * brightness, g * brightness, b * brightness)], True
