"""
Off Effect - Turn LEDs off
"""

from typing import List, Optional, Tuple
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState


class OffEffect(BaseEffect):
    """
    Off effect - all LEDs off.

    Simple effect that returns black (0, 0, 0) for all LEDs.
    """

    name = "off"
    description = "Turn off all LEDs"

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Return black for all LEDs.

        v1.5.0 fix: Returns per-LED colors to properly clear all LEDs.
        Previous implementation returned single color [(0,0,0)] which caused
        race conditions during state transitions from multi-LED effects.
        """
        return [(0.0, 0.0, 0.0)] * led_count, True
