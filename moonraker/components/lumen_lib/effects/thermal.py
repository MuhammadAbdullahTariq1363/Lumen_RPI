"""
Thermal Effect - Temperature-based progress bar
"""

from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState


def _lerp_color(color1: RGB, color2: RGB, t: float) -> RGB:
    """Linear interpolate between two colors. t=0 returns color1, t=1 returns color2."""
    r = color1[0] + (color2[0] - color1[0]) * t
    g = color1[1] + (color2[1] - color1[1]) * t
    b = color1[2] + (color2[2] - color1[2]) * t
    return (r, g, b)


def effect_fill(
    state: EffectState,
    fill_percent: float,
    led_count: int
) -> List[Optional[RGB]]:
    """
    Progressive fill effect with color gradient - core logic for thermal/progress effects.

    Creates a progress bar effect where LEDs light up sequentially with a smooth
    color gradient from start_color to end_color. Supports partial LED illumination
    for smooth visual transitions and configurable gradient curves.

    Args:
        state: Effect state with start_color, end_color, gradient_curve, direction
        fill_percent: Fill level from 0.0 (empty) to 1.0 (full)
        led_count: Total number of LEDs in the strip

    Returns:
        List of RGB tuples or None for each LED position
    """
    fill_percent = max(0.0, min(1.0, fill_percent))

    # How many LEDs should be lit (can be fractional for partial LED)
    lit_count = fill_percent * led_count

    colors: List[Optional[RGB]] = []

    for i in range(led_count):
        led_pos = i + 1  # 1-indexed position

        if led_pos <= lit_count:
            # This LED is fully lit
            if led_count <= 1:
                gradient_t = 1.0
            else:
                gradient_t = i / (led_count - 1)

            # Apply curve: t^curve makes gradient sharper at end when curve > 1
            curved_t = pow(gradient_t, state.gradient_curve)

            color = _lerp_color(state.start_color, state.end_color, curved_t)
            colors.append(color)

        elif led_pos - 1 < lit_count:
            # This LED is partially lit (the "leading edge")
            partial = lit_count - (led_pos - 1)  # 0.0-1.0 how much of this LED

            if led_count <= 1:
                gradient_t = 1.0
            else:
                gradient_t = i / (led_count - 1)

            curved_t = pow(gradient_t, state.gradient_curve)
            base_color = _lerp_color(state.start_color, state.end_color, curved_t)

            # Dim the color based on partial fill
            color = (base_color[0] * partial, base_color[1] * partial, base_color[2] * partial)
            colors.append(color)

        else:
            # This LED is off
            colors.append(None)

    # Reverse colors if direction is 'reverse'
    if hasattr(state, 'direction') and getattr(state, 'direction', 'standard') == 'reverse':
        colors = list(reversed(colors))
    return colors


class ThermalEffect(BaseEffect):
    """
    Temperature-based progressive fill effect - visualizes heating/cooling progress.

    Creates a visual temperature indicator that fills as temperature rises from
    ambient (temp_floor) to target. The fill percentage represents:
        (current_temp - temp_floor) / (target_temp - temp_floor)

    Common use cases:
    - Bed heating: ice (blue) → lava (red-orange)
    - Extruder heating: steel (gray) → fire (orange-red)
    - Cooldown: lava (red) → ice (blue) with reversed direction

    Parameters (from EffectState):
        - temp_source: 'bed', 'extruder', or 'chamber'
        - start_color: Color at temp_floor (cold)
        - end_color: Color at target_temp (hot)
        - gradient_curve: Non-linear gradient shape
        - direction: 'standard' or 'reverse'

    Requires state_data with:
        - {temp_source}_temp: Current temperature
        - {temp_source}_target: Target temperature
        - temp_floor: Ambient baseline temperature
    """

    name = "thermal"
    description = "Temperature-based gradient fill"
    requires_led_count = True
    requires_state_data = True

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate thermal gradient colors."""
        if not state_data:
            # No state data, show start color
            return [state.start_color] * led_count, True

        # Get temperature from state data
        temp_source = getattr(state, 'temp_source', 'extruder')
        current_temp = state_data.get(f'{temp_source}_temp', None)
        target_temp = state_data.get(f'{temp_source}_target', None)
        temp_floor = state_data.get('temp_floor', 25.0)

        # v1.5.0: Safety - Handle None temperatures (sensor failures, startup)
        if current_temp is None or target_temp is None:
            return [state.start_color] * led_count, True

        # If no target set, show solid start_color (waiting for heater)
        if target_temp <= 0:
            return [state.start_color] * led_count, True

        # If target is at or below floor, show start color
        if target_temp <= temp_floor:
            return [state.start_color] * led_count, True

        # v1.4.0: Critical - Calculate fill percentage with safety check
        temp_range = target_temp - temp_floor
        if temp_range <= 0:
            # Safety: If somehow temp_range is zero or negative, show start color
            return [state.start_color] * led_count, True

        temp_above_floor = current_temp - temp_floor
        fill_percent = temp_above_floor / temp_range

        return effect_fill(state, fill_percent, led_count), True
