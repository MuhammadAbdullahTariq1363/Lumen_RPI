"""
Solid Effect - Static color
"""

from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState


class SolidEffect(BaseEffect):
    """
    Solid color effect - constant static color.

    The simplest effect: shows a single color on all LEDs without animation.
    Color is taken from state.base_color.
    """

    name = "solid"
    description = "Static solid color on all LEDs"

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Return solid color for all LEDs."""
        # v1.4.6: Static effect - only needs update on first call (effect change)
        return [state.base_color], False
