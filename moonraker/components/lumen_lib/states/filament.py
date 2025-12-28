"""
Filament State Detector - Filament change/runout/load/unload

Detects when filament change operations are in progress.
Activated via macro tracking in lumen.cfg.
"""

from typing import Dict, Optional, Any
from .base import BaseStateDetector


class FilamentDetector(BaseStateDetector):
    """Detect filament change/runout state."""

    name = "filament"
    description = "Filament change/runout/load/unload in progress"
    priority = 10  # Medium priority - after error/printing, before heating

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Detect if filament change is active.

        Triggered by:
        1. Macro tracking when configured filament macros are detected
           in G-code responses (typically M600, FILAMENT_RUNOUT, LOAD_FILAMENT, UNLOAD_FILAMENT)
        2. v1.3.0 - Filament sensor detecting runout (filament_detected = False)

        Args:
            status: Printer status with optional filament_switch_sensor data
            context: Contains 'active_macro_state' set by macro tracking

        Returns:
            True if filament change macro is active or sensor detects runout
        """
        # Check macro tracking first (v1.2.0)
        if context and context.get('active_macro_state') == 'filament':
            return True

        # v1.3.0 - Check filament sensor for runout
        # Note: We only trigger on False (runout), not True (present)
        # None means no sensor installed - ignore
        filament_sensor = status.get('filament_switch_sensor filament_sensor', {})
        filament_detected = filament_sensor.get('filament_detected')
        if filament_detected is False:
            return True

        return False
