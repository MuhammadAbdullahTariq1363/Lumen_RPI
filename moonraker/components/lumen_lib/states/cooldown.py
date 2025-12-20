"""
Cooldown State Detector - Detects post-print cooling
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class CooldownDetector(BaseStateDetector):
    """
    Detects when printer is cooling down after a print.

    Detection logic:
        - Print job is complete (state="complete" or "cancelled")
        - Heater targets are 0 (turned off)
        - Current temps are above ambient (temp_floor)
        - Still hot enough to care about

    This state transitions to "idle" once temps drop to ambient levels.
    """

    name = "cooldown"
    description = "Cooling down after print completion"
    priority = 30

    COOLDOWN_THRESHOLD = 10.0  # Degrees above temp_floor to consider "cooling"

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if cooling down after print."""

        # Get temp_floor from context (default 25°C)
        temp_floor = 25.0
        if context:
            temp_floor = context.get('temp_floor', 25.0)

        # Check print state - should be complete or cancelled
        print_stats = status.get('print_stats', {})
        ps_state = print_stats.get('state', '').lower()

        if ps_state not in ['complete', 'cancelled', 'standby']:
            return False

        # Check that heaters are turned off (target = 0)
        extruder = status.get('extruder', {})
        ext_target = extruder.get('target', 0)

        heater_bed = status.get('heater_bed', {})
        bed_target = heater_bed.get('target', 0)

        # If any heater still has target, not cooling down (might be heating again)
        if ext_target > 0 or bed_target > 0:
            return False

        # Check if any heater is still hot (above temp_floor + threshold)
        ext_temp = extruder.get('temperature', 0)
        bed_temp = heater_bed.get('temperature', 0)

        cooldown_temp = temp_floor + self.COOLDOWN_THRESHOLD

        if ext_temp > cooldown_temp or bed_temp > cooldown_temp:
            return True

        return False
