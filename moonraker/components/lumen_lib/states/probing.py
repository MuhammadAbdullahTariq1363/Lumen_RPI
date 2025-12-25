"""
Probing State Detector - Probe calibration in progress

Detects when printer is performing probe calibration.
Activated via macro tracking in lumen.cfg.
"""

from typing import Dict, Optional, Any
from .base import BaseStateDetector


class ProbingDetector(BaseStateDetector):
    """Detect probe calibration state."""

    name = "probing"
    description = "Probe calibration in progress"
    priority = 5  # High priority - check before heating/idle

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Detect if probing is active.

        Triggered by macro tracking when configured probing macros are detected
        in G-code responses (typically PROBE_CALIBRATE).

        Args:
            status: Printer status (not used for macro-triggered states)
            context: Contains 'active_macro_state' set by macro tracking

        Returns:
            True if probing macro is active
        """
        if context and context.get('active_macro_state') == 'probing':
            return True
        return False
