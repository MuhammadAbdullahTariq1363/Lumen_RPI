"""
Idle State Detector - Detects ready/standby state
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class IdleDetector(BaseStateDetector):
    """
    Detects when printer is idle and ready for operation.

    Detection logic:
        - Not in any other state (fallback/default state)
        - All temps at or near ambient (temp_floor)
        - No active print job
        - No errors

    This is the lowest priority detector - if no other state matches,
    the printer is considered "idle".

    Common scenarios:
        - Printer just powered on and homed
        - Print finished and fully cooled
        - Waiting for next print
        - User browsing Mainsail/Fluidd
    """

    name = "idle"
    description = "Ready and waiting (default state)"
    priority = 100  # Lowest priority - fallback state

    TEMP_TOLERANCE = 5.0  # Degrees above temp_floor to consider "cool"

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if printer is idle."""

        # Get temp_floor from context (default 25°C)
        temp_floor = 25.0
        if context:
            temp_floor = context.get('temp_floor', 25.0)

        # Check that we're not in error state
        idle_timeout = status.get('idle_timeout', {})
        if idle_timeout.get('state', '').lower() == 'error':
            return False

        # Check that we're not printing
        print_stats = status.get('print_stats', {})
        ps_state = print_stats.get('state', '').lower()
        if ps_state in ['printing', 'paused']:
            return False

        # Check that no heaters have targets
        extruder = status.get('extruder', {})
        ext_target = extruder.get('target', 0)

        heater_bed = status.get('heater_bed', {})
        bed_target = heater_bed.get('target', 0)

        if ext_target > 0 or bed_target > 0:
            return False

        # Check that temps are near ambient (not cooling down from hot)
        ext_temp = extruder.get('temperature', 0)
        bed_temp = heater_bed.get('temperature', 0)

        idle_temp = temp_floor + self.TEMP_TOLERANCE

        if ext_temp > idle_temp or bed_temp > idle_temp:
            return False  # Still cooling down

        # If none of the above, we're idle
        return True
