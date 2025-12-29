"""
Heating State Detector - Detects heaters warming up
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector
import time


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

    v1.5.0: Added hysteresis to prevent flickering when targets
    temporarily drop during PRINT_START sequences.
    """

    name = "heating"
    description = "Heaters warming up to target temperature"
    priority = 20

    TEMP_TOLERANCE = 3.0  # Degrees C - considered "at temp" within this range
    HYSTERESIS_TIME = 10.0  # Seconds - stay in heating for this long even if targets drop

    def __init__(self):
        super().__init__()
        self._last_heating_time: Optional[float] = None  # When we last detected heating

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if any heater is actively heating.

        v1.5.0: Don't exit heating state if print has started - let printing state
        take over via priority system (printing=10, heating=20).

        v1.5.0: Added hysteresis - once heating starts, stay in heating for
        HYSTERESIS_TIME seconds even if targets temporarily drop. This prevents
        flickering during PRINT_START sequences that might clear/reset targets.
        """

        # v1.5.0: If print has started, let printing state take over (higher priority)
        print_stats = status.get('print_stats', {})
        ps_state = print_stats.get('state', '').lower()
        if ps_state in ['printing', 'paused']:
            # Print is active, heating state should yield to printing state
            self._last_heating_time = None  # Reset hysteresis
            return False

        # Check extruder
        extruder = status.get('extruder', {})
        ext_temp = extruder.get('temperature', 0)
        ext_target = extruder.get('target', 0)

        if ext_target > 0 and (ext_temp + self.TEMP_TOLERANCE) < ext_target:
            self._last_heating_time = time.time()
            return True

        # Check bed
        heater_bed = status.get('heater_bed', {})
        bed_temp = heater_bed.get('temperature', 0)
        bed_target = heater_bed.get('target', 0)

        if bed_target > 0 and (bed_temp + self.TEMP_TOLERANCE) < bed_target:
            self._last_heating_time = time.time()
            return True

        # Check chamber (if available)
        chamber = status.get('temperature_sensor chamber', {})
        if not chamber:
            # Try alternate chamber heater name
            chamber = status.get('heater_generic chamber', {})

        chamber_temp = chamber.get('temperature', 0)
        chamber_target = chamber.get('target', 0)

        if chamber_target > 0 and (chamber_temp + self.TEMP_TOLERANCE) < chamber_target:
            self._last_heating_time = time.time()
            return True

        # v1.5.0: Hysteresis - if we were heating recently, stay in heating
        # This prevents flickering when PRINT_START macros temporarily clear targets
        if self._last_heating_time is not None:
            elapsed = time.time() - self._last_heating_time
            if elapsed < self.HYSTERESIS_TIME:
                # Still within hysteresis window, stay in heating
                return True
            else:
                # Hysteresis expired, truly not heating anymore
                self._last_heating_time = None

        return False
