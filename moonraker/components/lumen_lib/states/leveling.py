"""
Leveling State Detector - Gantry/bed leveling in progress

Detects when printer is performing gantry or bed leveling.
Activated via macro tracking in lumen.cfg.
"""

from typing import Dict, Optional, Any
from .base import BaseStateDetector


class LevelingDetector(BaseStateDetector):
    """Detect gantry/bed leveling state."""

    name = "leveling"
    description = "Gantry or bed leveling in progress"
    priority = 5  # High priority - check before heating/idle

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Detect if leveling is active.

        Triggered by macro tracking when configured leveling macros are detected
        in G-code responses (typically QUAD_GANTRY_LEVEL or Z_TILT_ADJUST).

        Args:
            status: Printer status (not used for macro-triggered states)
            context: Contains 'active_macro_state' set by macro tracking

        Returns:
            True if leveling macro is active
        """
        if context and context.get('active_macro_state') == 'leveling':
            return True
        return False
