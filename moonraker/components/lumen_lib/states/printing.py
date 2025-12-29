"""
Printing State Detector - Detects active print job
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class PrintingDetector(BaseStateDetector):
    """
    Detects when printer is actively printing.

    Detection logic:
        - print_stats state is "printing" or "paused"
        - At target temperature (within tolerance)
        - Print file is loaded

    Note: Paused prints are considered "printing" state to maintain
    work lights and progress indicators. Future versions may split
    this into separate "paused" state.
    """

    name = "printing"
    description = "Active print job in progress"
    priority = 10  # High priority (after error)

    TEMP_TOLERANCE = 3.0  # Degrees C tolerance for "at temp"

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if actively printing.

        v1.5.0: Distinguish between "print job started" vs "actually printing layers".
        Stay in heating state during PRINT_START warmup, only switch to printing
        when actually laying down plastic.
        """

        print_stats = status.get('print_stats', {})
        ps_state = print_stats.get('state', '').lower()

        # Must be in printing or paused state
        if ps_state not in ['printing', 'paused']:
            return False

        # v1.5.0: Smart detection - has the print actually STARTED printing?
        # During PRINT_START, print_stats='printing' but we're still heating.
        # Only switch to printing state when we've made progress or temps are good.

        # Check 1: Has print made progress? (actually printing layers)
        display_status = status.get('display_status', {})
        progress = display_status.get('progress', 0.0)
        if progress > 0.0:
            # Print has made progress, definitely printing!
            return True

        # Check 2: Are we at temperature and ready to print?
        # This handles the transition from PRINT_START heating to actual printing
        extruder = status.get('extruder', {})
        ext_temp = extruder.get('temperature', 0)
        ext_target = extruder.get('target', 0)

        heater_bed = status.get('heater_bed', {})
        bed_temp = heater_bed.get('temperature', 0)
        bed_target = heater_bed.get('target', 0)

        # v1.5.0: Only check temps if we're actually heating something
        # If no heaters have targets, we can't be "at temp" - still in startup
        has_temp_target = (ext_target > 0) or (bed_target > 0)
        if not has_temp_target:
            # No temp targets set during print - still in PRINT_START initialization
            return False

        # Check if all heaters with targets are at temperature
        temps_ready = True
        if ext_target > 0:
            temps_ready = temps_ready and abs(ext_temp - ext_target) <= self.TEMP_TOLERANCE
        if bed_target > 0:
            temps_ready = temps_ready and abs(bed_temp - bed_target) <= self.TEMP_TOLERANCE

        if temps_ready:
            # Temps are at target, print is starting/about to start
            return True

        # print_stats='printing' but no progress yet and temps not ready
        # Still in PRINT_START heating phase - let heating state handle it
        return False
