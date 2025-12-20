"""
Heating State Detector - Detects heaters warming up
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class HeatingDetector(BaseStateDetector):
    """
    Detects when heaters are actively warming up to target temperature.

    Detection logic:
        - Any heater (bed, extruder, chamber) has target > 0
        - Current temp is below target (not yet reached)
        - Not already in "printing" state

    Common scenarios:
        - Preheat bed before print
        - Heat soak chamber
        - Nozzle warm-up during PRINT_START
    """

    name = "heating"
    description = "Heaters warming up to target temperature"
    priority = 20

    TEMP_TOLERANCE = 3.0  # Degrees C - considered "at temp" within this range

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if any heater is actively heating."""

        # Check extruder
        extruder = status.get('extruder', {})
        ext_temp = extruder.get('temperature', 0)
        ext_target = extruder.get('target', 0)

        if ext_target > 0 and (ext_temp + self.TEMP_TOLERANCE) < ext_target:
            return True

        # Check bed
        heater_bed = status.get('heater_bed', {})
        bed_temp = heater_bed.get('temperature', 0)
        bed_target = heater_bed.get('target', 0)

        if bed_target > 0 and (bed_temp + self.TEMP_TOLERANCE) < bed_target:
            return True

        # Check chamber (if available)
        chamber = status.get('temperature_sensor chamber', {})
        if not chamber:
            # Try alternate chamber heater name
            chamber = status.get('heater_generic chamber', {})

        chamber_temp = chamber.get('temperature', 0)
        chamber_target = chamber.get('target', 0)

        if chamber_target > 0 and (chamber_temp + self.TEMP_TOLERANCE) < chamber_target:
            return True

        return False
