"""
Progress Effect - Print progress bar
"""

from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState
from .thermal import effect_fill  # Reuse fill logic


class ProgressEffect(BaseEffect):
    """
    Print progress bar effect - visualizes print completion percentage.

    Creates a progress bar that fills as the print completes. The fill percentage
    represents the print_stats virtual_sdcard progress from Klipper.

    Common use cases:
    - Print progress: dark → bright color fill
    - Layer progress: with custom progress tracking
    - Time-based progress: elapsed/total time

    Parameters (from EffectState):
        - start_color: Color at 0% completion
        - end_color: Color at 100% completion
        - gradient_curve: Non-linear gradient shape (1.0=linear, >1=sharp at end)
        - direction: 'standard' or 'reverse'

    Requires state_data with:
        - print_progress: Float 0.0-1.0 (from virtual_sdcard or other source)
    """

    name = "progress"
    description = "Print progress gradient fill"
    requires_led_count = True
    requires_state_data = True

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate progress bar colors."""
        if not state_data:
            # No state data, show start color (0% progress)
            return [state.start_color] * led_count, True

        # Get progress from state data (0.0-1.0)
        progress = state_data.get('print_progress', 0.0)
        progress = max(0.0, min(1.0, progress))  # Clamp to valid range

        # Use shared fill logic from thermal effect
        return effect_fill(state, progress, led_count), True
