"""
Homing State Detector - G28 homing in progress

Detects when printer is homing (G28 or configured homing macro).
Activated via macro tracking in lumen.cfg.
"""

from typing import Dict, Optional, Any
from .base import BaseStateDetector


class HomingDetector(BaseStateDetector):
    """Detect homing state (G28 or custom homing macro)."""

    name = "homing"
    description = "Printer is homing axes"
    priority = 5  # High priority - check before heating/idle

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Detect if homing is active.

        Triggered by macro tracking when configured homing macros are detected
        in G-code responses (typically G28 or custom HOME macro).

        Args:
            status: Printer status (not used for macro-triggered states)
            context: Contains 'active_macro_state' set by macro tracking

        Returns:
            True if homing macro is active
        """
        if context and context.get('active_macro_state') == 'homing':
            return True
        return False
